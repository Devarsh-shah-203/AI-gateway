"""Provider-neutral browser chat transport built on Playwright.

The transport connects to an already-open browser, discovers a usable chat
composer from the DOM, inserts a prompt once, waits for a nearby submit control,
verifies submission, and extracts the resulting assistant response.

It intentionally does not require a particular hostname, textbox label, or
button label. Labels and common DOM attributes are used as optional hints, not
as hard requirements. Truly unusual interfaces may still need a small adapter.
"""

from __future__ import annotations

import re
import time
from typing import List, Optional, Tuple

from playwright.sync_api import Browser, Locator, Page


# These selectors deliberately describe common editable elements rather than a
# particular provider's label, hostname, or test ID.
_COMPOSER_SELECTOR = (
    "textarea:visible, "
    "[contenteditable='true']:visible, "
    "[role='textbox']:visible, "
    "input:not([type]):visible, "
    "input[type='text']:visible, "
    "input[type='search']:visible"
)

_BUTTON_SELECTOR = (
    "button:visible, [role='button']:visible, input[type='submit']:visible"
)

_ASSISTANT_SELECTORS = (
    '[data-message-author-role="assistant"], '
    '[data-role="assistant"], '
    '[data-author="assistant"], '
    '[data-message-role="assistant"], '
    '[data-testid*="assistant-message" i], '
    '[data-testid*="model-response" i], '
    '[class*="assistant-message" i], '
    '[class*="message-assistant" i], '
    'model-response'
)

_USER_SELECTORS = (
    '[data-message-author-role="user"], '
    '[data-role="user"], '
    '[data-author="user"], '
    '[data-message-role="user"]'
)

# Used only when the page does not expose a clear assistant/model marker.
# Selector priority matters: prefer turn/message containers over arbitrary text.
_GENERIC_MESSAGE_SELECTORS = (
    '[data-testid*="conversation-turn" i]',
    '[data-testid*="message" i]',
    '[data-testid*="response" i]',
    'model-response',
    'article',
    '[role="article"]',
    '[role="log"] > *',
    '[role="feed"] > *',
    '[class*="message-content" i]',
    '[class*="markdown" i]',
    '[class*="prose" i]',
    '[class*="assistant" i]',
    '[class*="answer" i]',
    '[class*="response" i]'
)

_DIALOG_SELECTOR = (
    '[role="alertdialog"]:visible, '
    '[role="dialog"]:visible, '
    '[aria-modal="true"]:visible'
)


class BrowserChat:
    """Interact with a browser-based chat interface without provider labels."""

    def __init__(
        self,
        browser: Browser,
        page: Optional[Page] = None,
        *,
        composer_timeout: float = 15.0,
        insertion_timeout: float = 30.0,
        send_timeout: float = 30.0,
        submission_timeout: float = 12.0,
        response_timeout: float = 180.0,
        image_generation_timeout: float = 600.0,
        response_stability: float = 2.5,
        poll_interval: float = 0.25,
    ) -> None:
        self.browser = browser
        self.composer_timeout = composer_timeout
        self.insertion_timeout = insertion_timeout
        self.send_timeout = send_timeout
        self.submission_timeout = submission_timeout
        self.response_timeout = response_timeout
        # Image generation can take substantially longer than ordinary text
        # responses. This timeout is used only when the outgoing prompt appears
        # to explicitly request generated visual content.
        self.image_generation_timeout = image_generation_timeout
        self.response_stability = response_stability
        self.poll_interval = poll_interval
        self._active_prompt: Optional[str] = None
        self._active_image_generation = False

        self.page = page or self._find_chat_page()
        if self.page is None:
            raise RuntimeError(
                "No browser page is available. Open the target chat page and try again."
            )

    # ------------------------------------------------------------------
    # PAGE AND COMPOSER DISCOVERY
    # ------------------------------------------------------------------

    def _find_chat_page(self) -> Optional[Page]:
        """Choose the open page with the strongest editable-composer signal.

        URL and page title are intentionally not required. If a chat composer is
        not available yet (for example, a sign-in page is open), fall back to the
        most recently opened non-blank page so send_prompt can return a useful
        readiness error rather than failing during object construction.
        """
        pages: List[Page] = []
        for context in self.browser.contexts:
            for page in context.pages:
                try:
                    if not page.is_closed():
                        pages.append(page)
                except Exception:
                    continue

        if not pages:
            return None

        best_page: Optional[Page] = None
        best_score = float("-inf")

        for page in pages:
            try:
                _locator, score = self._find_composer_on_page(
                    page, require_ready=False
                )
                if score is None:
                    score = -1000
                # Prefer a page that already looks like a conversation when
                # composer quality is otherwise similar.
                if page.locator(
                    '[role="log"], [role="feed"], article, '
                    '[data-testid*="conversation-turn" i]'
                ).count():
                    score += 8
                if score > best_score:
                    best_page = page
                    best_score = score
            except Exception:
                continue

        if best_page is not None and best_score >= 28:
            return best_page

        for page in reversed(pages):
            try:
                if page.url and page.url != "about:blank":
                    return page
            except Exception:
                continue
        return pages[-1]

    @staticmethod
    def _composer_score(locator: Locator) -> int:
        """Score an element structurally; visible labels are optional hints."""
        try:
            return int(
                locator.evaluate(
                    """(el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        const tag = (el.tagName || '').toLowerCase();
                        const type = (el.getAttribute('type') || '').toLowerCase();
                        const role = (el.getAttribute('role') || '').toLowerCase();
                        const label = [
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('placeholder') || '',
                            el.getAttribute('title') || ''
                        ].join(' ').toLowerCase();
                        let score = 0;

                        if (el.isContentEditable) score += 75;
                        else if (tag === 'textarea') score += 65;
                        else if (role === 'textbox') score += 45;
                        else if (tag === 'input') score += 18;

                        if (type === 'search' || /search|find/.test(label)) score -= 28;
                        if (/password|e-mail|email|username|sign in|log in/.test(label)) score -= 35;
                        if (/message|chat|prompt|reply|ask/.test(label)) score += 8;

                        if (rect.width >= 350) score += 18;
                        else if (rect.width >= 180) score += 10;
                        else if (rect.width < 90) score -= 12;
                        if (rect.height >= 28) score += 5;
                        if (rect.bottom >= window.innerHeight * 0.55) score += 12;
                        if (rect.bottom >= window.innerHeight * 0.78) score += 6;
                        if (style.display === 'none' || style.visibility === 'hidden') score -= 100;
                        if (el.disabled || el.getAttribute('aria-disabled') === 'true') score -= 18;
                        if (el.readOnly) score -= 30;

                        const form = el.closest('form');
                        if (form && form.querySelector('button, [role="button"], input[type="submit"]')) {
                            score += 12;
                        }
                        return score;
                    }"""
                )
            )
        except Exception:
            return -1000

    def _find_composer_on_page(
        self,
        page: Page,
        *,
        require_ready: bool = True,
    ) -> Tuple[Optional[Locator], Optional[int]]:
        """Return the highest-scoring visible composer candidate on a page."""
        try:
            candidates = page.locator(_COMPOSER_SELECTOR)
            candidate_count = candidates.count()
        except Exception:
            return None, None

        best_locator: Optional[Locator] = None
        best_score: Optional[int] = None

        for index in range(candidate_count):
            candidate = candidates.nth(index)
            try:
                if not candidate.is_visible():
                    continue
                if require_ready and (
                    not candidate.is_enabled() or not candidate.is_editable()
                ):
                    continue
                score = self._composer_score(candidate)
                if score < 25:
                    continue
                if best_score is None or score > best_score:
                    best_locator = candidate
                    best_score = score
            except Exception:
                continue

        return best_locator, best_score

    def get_textbox(self) -> Locator:
        """Return the best composer candidate (legacy method name retained)."""
        locator, _score = self._find_composer_on_page(
            self.page, require_ready=False
        )
        if locator is not None:
            return locator
        # Return a valid, empty locator rather than None for callers that inspect
        # count()/wait_for() on this legacy method.
        return self.page.locator(".__ai_gateway_missing_composer__")

    def check_textbox_ready(self) -> Tuple[bool, str]:
        """Return readiness and a readable explanation, for compatibility."""
        locator, _score = self._find_composer_on_page(
            self.page, require_ready=True
        )
        if locator is None:
            return False, "No visible, editable chat composer was found."
        return True, ""

    def _wait_for_composer(self, timeout: float) -> Optional[Locator]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            locator, _score = self._find_composer_on_page(
                self.page, require_ready=True
            )
            if locator is not None:
                return locator
            time.sleep(self.poll_interval)
        return None

    @staticmethod
    def _read_composer_text(locator: Locator) -> str:
        try:
            tag = locator.evaluate("el => (el.tagName || '').toLowerCase()")
            if tag in {"input", "textarea"}:
                return locator.input_value()
            return locator.inner_text()
        except Exception:
            return ""

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join((value or "").split())

    def _wait_for_prompt_in_composer(self, prompt: str, timeout: float) -> bool:
        expected = self._normalize_text(prompt)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            locator, _score = self._find_composer_on_page(
                self.page, require_ready=False
            )
            if locator is not None:
                current = self._normalize_text(self._read_composer_text(locator))
                if current == expected:
                    return True
            time.sleep(self.poll_interval)
        return False

    # ------------------------------------------------------------------
    # SEND CONTROL DISCOVERY
    # ------------------------------------------------------------------

    def _find_send_button(self, composer: Locator) -> Tuple[Optional[Locator], bool]:
        """Find the submit control structurally, without requiring its label.

        Buttons near the composer, inside its form/container, or aligned with its
        lower-right edge rank highest. Send-like labels are positive hints only;
        clearly unrelated controls (microphone, attachment, stop, etc.) are down-
        ranked so an unlabeled icon button can still be selected.
        """
        try:
            ranked = composer.evaluate(
                """editor => {
                    const selector = 'button, [role="button"], input[type="submit"]';
                    const visible = (el) => {
                        const r = el.getBoundingClientRect();
                        const s = window.getComputedStyle(el);
                        return r.width > 0 && r.height > 0 &&
                            s.display !== 'none' && s.visibility !== 'hidden';
                    };
                    const er = editor.getBoundingClientRect();
                    const editorForm = editor.closest('form');
                    const buttons = Array.from(document.querySelectorAll(selector)).filter(visible);

                    return buttons.map((button, index) => {
                        const br = button.getBoundingClientRect();
                        const label = [
                            button.innerText || '',
                            button.getAttribute('aria-label') || '',
                            button.getAttribute('title') || '',
                            button.getAttribute('data-testid') || '',
                            button.getAttribute('value') || ''
                        ].join(' ').toLowerCase();
                        let score = 0;

                        if (editorForm && editorForm.contains(button)) score += 48;

                        let ancestor = editor.parentElement;
                        let depth = 0;
                        while (ancestor && depth < 6) {
                            if (ancestor.contains(button)) {
                                score += Math.max(0, 27 - depth * 4);
                                break;
                            }
                            ancestor = ancestor.parentElement;
                            depth += 1;
                        }

                        const dx = Math.max(0, Math.max(er.left - br.right, br.left - er.right));
                        const dy = Math.max(0, Math.max(er.top - br.bottom, br.top - er.bottom));
                        const distance = Math.hypot(dx, dy);
                        if (distance < 35) score += 22;
                        else if (distance < 90) score += 15;
                        else if (distance < 180) score += 8;
                        else if (distance > 550) score -= 35;

                        if (Math.abs(br.right - er.right) < 135) score += 8;
                        if (br.bottom >= er.top - 80 && br.top <= er.bottom + 120) score += 7;
                        if ((button.getAttribute('type') || '').toLowerCase() === 'submit') score += 24;
                        if (/\\b(send|submit|ask|reply)\\b/.test(label)) score += 32;
                        if (/\\b(voice|microphone|dictation|attach|upload|stop generating|cancel generation|new chat|search)\\b/.test(label)) score -= 45;

                        return {
                            index,
                            score,
                            disabled: !!button.disabled || button.getAttribute('aria-disabled') === 'true'
                        };
                    }).sort((a, b) => b.score - a.score);
                }"""
            )
        except Exception:
            return None, False

        if not ranked:
            return None, False
        best = ranked[0]
        # A button with no meaningful relationship to the composer is not safe
        # to click. The threshold is low enough for an unlabeled nearby icon.
        if best.get("score", -1000) < 15:
            return None, False

        try:
            button = self.page.locator(_BUTTON_SELECTOR).nth(int(best["index"]))
            return button, bool(button.is_enabled()) and not bool(best.get("disabled"))
        except Exception:
            return None, False

    # ------------------------------------------------------------------
    # RESPONSE EXTRACTION
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_element_text(locator: Locator) -> str:
        """Extract readable text while preserving line breaks and code blocks."""
        try:
            value = locator.evaluate(
                r"""element => {
                    const clone = element.cloneNode(true);
                    clone.querySelectorAll(
                        'button, [role="button"], svg, nav, footer, [aria-hidden="true"], [data-copy-button]'
                    ).forEach(node => node.remove());

                    // Replace code blocks with placeholders before normalizing
                    // surrounding prose, so blank lines/indentation in code stay intact.
                    const codeBlocks = [];
                    clone.querySelectorAll('pre').forEach(pre => {
                        const code = pre.querySelector('code');
                        const content = code ? (code.textContent || '') : (pre.textContent || '');
                        const token = `__AI_GATEWAY_CODE_BLOCK_${codeBlocks.length}__`;
                        codeBlocks.push(content);
                        pre.replaceWith(document.createTextNode(token));
                    });

                    const blockTags = new Set([
                        'address', 'article', 'blockquote', 'dd', 'div', 'dl', 'dt',
                        'fieldset', 'figcaption', 'figure', 'h1', 'h2', 'h3', 'h4',
                        'h5', 'h6', 'li', 'ol', 'p', 'section', 'table', 'tbody',
                        'td', 'th', 'tr', 'ul'
                    ]);

                    function readNode(node) {
                        if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || '';
                        if (node.nodeType !== Node.ELEMENT_NODE) return '';
                        const tag = node.tagName.toLowerCase();
                        if (tag === 'br') return '\n';
                        const children = Array.from(node.childNodes).map(readNode).join('');
                        return blockTags.has(tag) ? '\n' + children + '\n' : children;
                    }

                    let text = readNode(clone).replace(/\r\n/g, '\n');
                    text = text.replace(/\n{3,}/g, '\n\n');
                    text = text.replace(/^\n+|\n+$/g, '');

                    codeBlocks.forEach((content, index) => {
                        const token = `__AI_GATEWAY_CODE_BLOCK_${index}__`;
                        text = text.replace(token, '\n' + content + '\n');
                    });
                    return text;
                }"""
            )
            return value or ""
        except Exception:
            try:
                return locator.inner_text().strip()
            except Exception:
                return ""

    def get_assistant_messages(self) -> Locator:
        """Return commonly marked assistant/model response elements."""
        return self.page.locator(_ASSISTANT_SELECTORS)

    def _generic_message_items(self) -> List[Tuple[Locator, str]]:
        """Return message-like elements from the first useful generic selector.

        The active outgoing prompt is excluded so a user bubble is not mistaken
        for the model's reply when a page provides no explicit role markers.
        """
        active_prompt = self._normalize_text(self._active_prompt or "")

        for selector in _GENERIC_MESSAGE_SELECTORS:
            items: List[Tuple[Locator, str]] = []
            try:
                matches = self.page.locator(selector)
                count = matches.count()
            except Exception:
                continue

            for index in range(count):
                item = matches.nth(index)
                try:
                    if not item.is_visible():
                        continue
                    text = self._extract_element_text(item)
                    normalized = self._normalize_text(text)
                    if not normalized:
                        continue
                    # Exclude a generic bubble whose content is the outgoing prompt.
                    # Do not exclude every message that CONTAINS the prompt: a valid
                    # assistant answer may quote or echo the user's text verbatim.
                    # Marked user-only containers are filtered separately below.
                    if active_prompt and normalized == active_prompt:
                        continue
                    # Some sites mark user messages in an ancestor while their
                    # generic selector also matches that ancestor. Avoid treating
                    # that node as a model response.
                    try:
                        is_user_only = item.evaluate(
                            """el => {
                                const user = el.matches(
                                    '[data-message-author-role=\"user\"], [data-role=\"user\"], [data-author=\"user\"], [data-message-role=\"user\"]'
                                ) || el.querySelector(
                                    '[data-message-author-role=\"user\"], [data-role=\"user\"], [data-author=\"user\"], [data-message-role=\"user\"]'
                                );
                                const assistant = el.matches(
                                    '[data-message-author-role=\"assistant\"], [data-role=\"assistant\"], [data-author=\"assistant\"], [data-message-role=\"assistant\"]'
                                ) || el.querySelector(
                                    '[data-message-author-role=\"assistant\"], [data-role=\"assistant\"], [data-author=\"assistant\"], [data-message-role=\"assistant\"]'
                                );
                                return !!user && !assistant;
                            }"""
                        )
                    except Exception:
                        is_user_only = False
                    if is_user_only:
                        continue
                    items.append((item, text))
                except Exception:
                    continue

            if items:
                return items
        return []

    def _assistant_count(self) -> int:
        try:
            return self.get_assistant_messages().count()
        except Exception:
            return 0

    @staticmethod
    def _is_image_generation_request(prompt: str) -> bool:
        """Return whether the request explicitly asks the model to create visuals.

        This is intentionally a conservative heuristic: it affects timeout
        selection and whether newly rendered response images are reported as
        generated outputs, so ordinary web/article thumbnails should not trigger
        it merely because the prompt contains the word "image".
        """
        text = (prompt or "").lower()
        visual_nouns = (
            r"image|picture|illustration|artwork|photo|photograph|graphic|"
            r"logo|icon|wallpaper|poster|banner|thumbnail|visual|diagram|"
            r"drawing|painting|portrait|concept art|character|mascot|mockup|"
            r"flyer|infographic|cover|sticker|emblem|avatar|sprite"
        )
        creation_verbs = r"generate|create|draw|make|design|render|paint|illustrate|produce"
        if re.search(
            rf"\b(?:{creation_verbs})\b.{{0,160}}\b(?:{visual_nouns})\b",
            text,
            re.S,
        ):
            return True
        if re.search(r"\b(?:draw|paint|illustrate)\b.{0,100}", text, re.S):
            return True
        if re.search(
            rf"\b(?:{visual_nouns})\b.{{0,100}}\b(?:{creation_verbs})\b",
            text,
            re.S,
        ):
            return True
        # Some natural requests omit an explicit creation verb, e.g. "visual of BIT"
        # or "diagram of a segment tree". Treat these as potential image-generation
        # requests so they receive the longer timeout from the start.
        if re.search(
            r"\b(?:visual|image|picture|illustration|diagram|drawing|chart|infographic|"
            r"poster|wallpaper|logo|icon|portrait)\s+(?:of|for|showing)\b",
            text,
        ):
            return True
        if re.search(
            r"\b(?:show|give)\s+(?:me\s+)?(?:a|an)?\s*"
            r"(?:visual|image|picture|illustration|diagram|drawing|chart)\b",
            text,
        ):
            return True
        return False

    def _latest_response_locator(
        self,
        previous_assistant_count: Optional[int] = None,
        previous_generic_count: Optional[int] = None,
        previous_text: str = "",
    ) -> Optional[Locator]:
        """Locate the newest assistant response, including an image-only turn."""
        try:
            messages = self.get_assistant_messages()
            count = messages.count()
            if count and (
                previous_assistant_count is None
                or count > previous_assistant_count
            ):
                for index in range(count - 1, -1, -1):
                    candidate = messages.nth(index)
                    try:
                        if candidate.is_visible():
                            return candidate
                    except Exception:
                        continue
        except Exception:
            pass

        try:
            items = self._generic_message_items()
            if items:
                if (
                    previous_generic_count is not None
                    and len(items) > previous_generic_count
                ) or (
                    previous_text
                    and self._normalize_text(items[-1][1])
                    != self._normalize_text(previous_text)
                ):
                    return items[-1][0]
        except Exception:
            pass

        try:
            messages = self.get_assistant_messages()
            for index in range(messages.count() - 1, -1, -1):
                candidate = messages.nth(index)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        except Exception:
            pass
        try:
            items = self._generic_message_items()
            if items:
                return items[-1][0]
        except Exception:
            pass
        return None

    def _response_media_signature(
        self,
        previous_assistant_count: Optional[int] = None,
        previous_generic_count: Optional[int] = None,
        previous_text: str = "",
    ) -> Tuple[str, ...]:
        """Describe sizeable image/media elements in the latest assistant turn."""
        locator = self._latest_response_locator(
            previous_assistant_count=previous_assistant_count,
            previous_generic_count=previous_generic_count,
            previous_text=previous_text,
        )
        if locator is None:
            return ()
        try:
            entries = locator.evaluate(
                r"""root => {
                    const selector = 'img, canvas, video, [style*="background-image"]';
                    const nodes = [];
                    if (root.matches && root.matches(selector)) nodes.push(root);
                    nodes.push(...root.querySelectorAll(selector));
                    return nodes.map(node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        const width = Math.max(rect.width || 0, node.naturalWidth || 0, node.videoWidth || 0);
                        const height = Math.max(rect.height || 0, node.naturalHeight || 0, node.videoHeight || 0);
                        const visible = rect.width > 0 && rect.height > 0 &&
                            style.display !== 'none' && style.visibility !== 'hidden';
                        if (!visible || width < 80 || height < 80) return null;
                        return [
                            (node.tagName || '').toLowerCase(),
                            node.currentSrc || node.src || '',
                            node.getAttribute('alt') || '',
                            node.getAttribute('title') || '',
                            Math.round(width), Math.round(height),
                            node.complete === false ? 'loading' : 'ready'
                        ].join('|');
                    }).filter(Boolean);
                }"""
            )
            return tuple(str(entry) for entry in entries or [])
        except Exception:
            return ()

    def _generated_image_signature(self) -> Tuple[str, ...]:
        """Return visible image-output markers created by the chat UI.

        Prefer explicit generated-image markers over arbitrary <img> elements:
        web previews and article thumbnails should not trigger an image-generated
        notification. ChatGPT currently exposes these as elements such as
        [data-testid="generated-image-preview"] with an accessible label.
        """
        selector = (
            '[data-testid="generated-image-preview"], '
            '[aria-label^="Generated image" i]'
        )
        try:
            nodes = self.page.locator(selector)
            count = nodes.count()
        except Exception:
            return ()

        entries: List[str] = []
        for index in range(count):
            node = nodes.nth(index)
            try:
                result = node.evaluate(
                    r"""node => {
                        const image = node.matches('img') ? node : node.querySelector('img');
                        const visual = image || node;
                        const rect = visual.getBoundingClientRect();
                        const style = window.getComputedStyle(visual);
                        const visible = rect.width > 0 && rect.height > 0 &&
                            style.display !== 'none' && style.visibility !== 'hidden';
                        if (!visible) return null;

                        const label = node.getAttribute('aria-label') ||
                            node.getAttribute('title') ||
                            (image && (image.getAttribute('alt') || image.getAttribute('title'))) ||
                            'generated-image';
                        const src = image ? (image.currentSrc || image.src || '') : '';
                        const width = Math.round(Math.max(rect.width || 0, image?.naturalWidth || 0));
                        const height = Math.round(Math.max(rect.height || 0, image?.naturalHeight || 0));
                        if (width < 50 || height < 50) return null;

                        const ready = !!image && image.complete && image.naturalWidth > 0;
                        // `key` remains stable as a loading image becomes ready.
                        const key = [label, src || 'pending', width, height].join('|');
                        return { key, ready };
                    }"""
                )
                if result and result.get('key'):
                    state = 'ready' if result.get('ready') else 'loading'
                    entries.append(f"{result['key']}|{state}")
            except Exception:
                continue
        return tuple(entries)

    @staticmethod
    def _media_keys(signature: Tuple[str, ...]) -> set[str]:
        """Strip the loading/ready suffix so load progress isn't a new image."""
        return {entry.rsplit('|', 1)[0] for entry in signature}

    def get_latest_assistant_text(self) -> str:
        """Read the latest reply, preferring current-turn generic nodes in flight.

        Some providers leave older assistant-role nodes in the DOM while using a
        different structure for the newest reply. During an active request, search
        the generic message candidates first so an old marked response cannot hide
        a newly rendered unmarked response. The active user prompt is filtered out
        by _generic_message_items().
        """
        if self._active_prompt:
            generic_items = self._generic_message_items()
            if generic_items:
                return generic_items[-1][1]

        try:
            messages = self.get_assistant_messages()
            for index in range(messages.count() - 1, -1, -1):
                message = messages.nth(index)
                try:
                    if not message.is_visible():
                        continue
                    text = self._extract_element_text(message)
                    if text:
                        return text
                except Exception:
                    continue
        except Exception:
            pass

        generic_items = self._generic_message_items()
        if generic_items:
            return generic_items[-1][1]
        return ""

    def detect_page_state(self) -> Tuple[Optional[str], Optional[str]]:
        """Detect visible dialogs indicating a blocked or interrupted request."""
        try:
            dialogs = self.page.locator(_DIALOG_SELECTOR)
            dialog_count = dialogs.count()
        except Exception:
            return None, None

        for index in range(dialog_count):
            dialog = dialogs.nth(index)
            try:
                text = dialog.inner_text().strip()
            except Exception:
                text = ""
            if not text:
                continue

            lower = text.lower()
            if any(
                keyword in lower
                for keyword in (
                    "usage limit",
                    "reached your limit",
                    "limit reached",
                    "message limit",
                    "rate limit",
                    "too many requests",
                    "you've run out",
                )
            ):
                return "RATE_LIMITED", text

            if any(
                keyword in lower
                for keyword in (
                    "session expired",
                    "please sign in",
                    "please log in",
                    "authentication required",
                    "your session has expired",
                )
            ):
                return "AUTH_REQUIRED", text

            return "USER_ACTION_REQUIRED", text

        # Keep URL checks generic and use them only as a fallback clue.
        try:
            if re.search(r"/(login|log-in|signin|sign-in|authenticate)(/|$|\?)", self.page.url, re.I):
                return "AUTH_REQUIRED", "The current page appears to require authentication."
        except Exception:
            pass

        return None, None

    def _is_generation_active(self) -> bool:
        """Look for generic busy/stop signals before treating stable text as final."""
        try:
            controls = self.page.locator(_BUTTON_SELECTOR)
            for index in range(controls.count()):
                control = controls.nth(index)
                try:
                    if not control.is_visible():
                        continue
                    label = control.evaluate(
                        """el => [
                            el.innerText || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || '',
                            el.getAttribute('data-testid') || ''
                        ].join(' ').toLowerCase().trim()"""
                    )
                    if re.search(
                        r"\b(stop generating|stop generation|stop response|stop streaming|cancel generation|interrupt response)\b",
                        label,
                    ) or label == "stop":
                        return True
                except Exception:
                    continue

            busy = self.page.locator(
                '[aria-busy="true"]:visible, '
                '[data-streaming="true"]:visible, '
                '[data-loading="true"]:visible'
            )
            if busy.count() > 0:
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # SUBMISSION VERIFICATION
    # ------------------------------------------------------------------

    def _user_message_count(self) -> int:
        try:
            return self.page.locator(", ".join(_USER_SELECTORS)).count()
        except Exception:
            return 0

    def _prompt_is_visible_as_user_message(self, prompt: str) -> bool:
        expected = self._normalize_text(prompt)
        if not expected:
            return False

        selectors = list(_USER_SELECTORS) + list(_GENERIC_MESSAGE_SELECTORS)
        for selector in selectors:
            try:
                matches = self.page.locator(selector)
                for index in range(matches.count() - 1, -1, -1):
                    item = matches.nth(index)
                    try:
                        if not item.is_visible():
                            continue
                        content = self._normalize_text(self._extract_element_text(item))
                        if expected and expected in content:
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    def _wait_for_submission(
        self,
        prompt: str,
        previous_user_count: int,
        previous_text: str = "",
        previous_assistant_count: Optional[int] = None,
        previous_generic_count: Optional[int] = None,
    ) -> bool:
        """Confirm submission from the outgoing turn, composer, or new response.

        Some chat UIs do not expose a user-message node or clear the composer in
        a way our existing checks can detect. A newly appearing assistant reply
        is also strong evidence that the click was accepted. These checks only
        observe the page; they never click Send again.
        """
        deadline = time.monotonic() + self.submission_timeout
        composer_clear_since: Optional[float] = None
        expected = self._normalize_text(prompt)

        while time.monotonic() < deadline:
            if self._prompt_is_visible_as_user_message(prompt):
                return True

            try:
                current_count = self._user_message_count()
                if current_count > previous_user_count:
                    # Prefer matching the actual outgoing text, but retain the
                    # count as a fallback signal for UIs that transform messages.
                    if self._prompt_is_visible_as_user_message(prompt):
                        return True
            except Exception:
                pass

            # A response can begin even when user-message discovery fails. Check
            # against the pre-click baseline so an older answer is not enough.
            try:
                current_text = self.get_latest_assistant_text()
                current_assistant_count = self._assistant_count()
                current_generic_count = len(self._generic_message_items())

                new_assistant_node = (
                    previous_assistant_count is not None
                    and current_assistant_count > previous_assistant_count
                )
                new_generic_node = (
                    previous_generic_count is not None
                    and current_generic_count > previous_generic_count
                )
                new_assistant_text = bool(
                    current_text and current_text != previous_text
                )

                if new_assistant_node or new_generic_node or new_assistant_text:
                    return True
            except Exception:
                # Keep the established submission signals available even if a
                # provider's response DOM cannot be inspected during this poll.
                pass

            composer, _score = self._find_composer_on_page(
                self.page, require_ready=False
            )
            if composer is not None:
                current = self._normalize_text(self._read_composer_text(composer))
                if current != expected:
                    if not current:
                        if composer_clear_since is None:
                            composer_clear_since = time.monotonic()
                        elif time.monotonic() - composer_clear_since >= 1.0:
                            # Composer clearing after a single click is strong
                            # evidence of acceptance, even if turns are virtualized.
                            return True
                    else:
                        composer_clear_since = None

            time.sleep(self.poll_interval)
        return False

    def _response_diagnostic(self, latest_text: str = "") -> str:
        """Describe detector state without dumping the prompt or answer text."""
        try:
            title = self.page.title()
        except Exception:
            title = "<unavailable>"
        try:
            generic_count = len(self._generic_message_items())
        except Exception:
            generic_count = -1
        try:
            assistant_count = self._assistant_count()
        except Exception:
            assistant_count = -1
        try:
            active = self._is_generation_active()
        except Exception:
            active = False
        return (
            f"page_title={title!r}, assistant_nodes={assistant_count}, "
            f"generic_candidates={generic_count}, latest_text_chars={len(latest_text)}, "
            f"generation_active={active}"
        )

    # ------------------------------------------------------------------
    # MAIN SEND / WAIT FLOW
    # ------------------------------------------------------------------

    def wait_for_response(
        self,
        previous_text: str,
        previous_assistant_count: Optional[int] = None,
        previous_generic_count: Optional[int] = None,
        previous_media_signature: Tuple[str, ...] = (),
    ) -> Tuple[str, str]:
        """Wait for a new assistant response and return its readable text.

        Explicit image-generation requests receive a longer timeout. The waiter
        also detects an image-only assistant turn, reports it in the terminal,
        and returns any accompanying assistant text for the CLI to display.
        """
        start = time.monotonic()
        timeout = (
            self.image_generation_timeout
            if self._active_image_generation
            else self.response_timeout
        )
        saw_new_response = False
        last_text = previous_text
        last_media_signature = previous_media_signature
        stable_since: Optional[float] = None
        next_status_report = start + 10.0
        image_output_seen = False
        image_notice_printed = False

        if self._active_image_generation:
            print(
                "Image-generation request detected. Waiting up to "
                f"{timeout:g} seconds for the response and image output."
            )

        print(
            "Response detector armed: "
            f"assistant_nodes={self._assistant_count()}, "
            f"generic_candidates={len(self._generic_message_items())}."
        )

        while True:
            state, information = self.detect_page_state()
            current_text = self.get_latest_assistant_text()
            assistant_count = self._assistant_count()
            generic_count = len(self._generic_message_items())
            # Search for explicit generated-image markers on every turn, not only
            # when the prompt heuristic predicted image generation. Natural prompts
            # like "visual of BIT" can still cause the model to generate an image.
            current_media_signature = self._generated_image_signature()

            structured_response_added = (
                previous_assistant_count is not None
                and assistant_count > previous_assistant_count
            )
            generic_response_added = (
                previous_generic_count is not None
                and generic_count > previous_generic_count
            )
            new_media_response = bool(
                self._media_keys(current_media_signature)
                - self._media_keys(previous_media_signature)
            ) and not image_output_seen
            if self._active_image_generation or new_media_response or image_output_seen:
                if new_media_response:
                    # An actual generated-image DOM marker is stronger evidence
                    # than prompt wording. Extend the wait even for implicit requests.
                    self._active_image_generation = True
                    timeout = max(timeout, self.image_generation_timeout)
                if new_media_response or image_output_seen:
                # get_latest_assistant_text() may fall back to an older non-empty
                # generic message when the new assistant turn contains only an
                # image. Once media appears, keep reading the current response
                # container on each poll so an old answer is never reused.
                    response_locator = self._latest_response_locator(
                        previous_assistant_count=previous_assistant_count,
                        previous_generic_count=previous_generic_count,
                        previous_text=previous_text,
                    )
                    if response_locator is not None:
                        current_turn_text = self._extract_element_text(response_locator)
                        if current_turn_text and self._normalize_text(current_turn_text) != self._normalize_text(previous_text):
                            current_text = current_turn_text
                        elif current_text == previous_text:
                            # Never return stale text from the preceding turn for an
                            # image-only response that has no readable message text.
                            current_text = ""

            new_text_response = bool(current_text and current_text != previous_text)

            if (
                structured_response_added
                or generic_response_added
                or new_text_response
                or new_media_response
            ):
                saw_new_response = True

            if new_media_response:
                image_output_seen = True
                if not image_notice_printed:
                    print(
                        "\n[IMAGE OUTPUT DETECTED] The model generated an image. "
                        "It is available in the browser. Waiting for the response "
                        "and image to finish..."
                    )
                    image_notice_printed = True

            # Some interfaces place image previews in dialog-like overlays. Once
            # an actual new image output is observed, don't misclassify that
            # preview as a request for user input.
            if state in {"RATE_LIMITED", "AUTH_REQUIRED", "USER_ACTION_REQUIRED"}:
                if not (
                    self._active_image_generation
                    and image_output_seen
                    and state == "USER_ACTION_REQUIRED"
                ):
                    return state, information or ""

            image_media_ready = bool(current_media_signature) and all(
                item.endswith("|ready") for item in current_media_signature
            )
            now = time.monotonic()
            if saw_new_response and (current_text or image_output_seen):
                content_changed = (
                    current_text != last_text
                    or current_media_signature != last_media_signature
                )
                if content_changed:
                    last_text = current_text
                    last_media_signature = current_media_signature
                    stable_since = now
                elif stable_since is None:
                    stable_since = now

                if (
                    stable_since is not None
                    and now - stable_since >= self.response_stability
                    and not self._is_generation_active()
                    and (not image_output_seen or image_media_ready)
                ):
                    result = current_text.strip()
                    if image_output_seen:
                        image_note = (
                            "[IMAGE GENERATED] An image output is available in the "
                            "browser. Open the browser to view it."
                        )
                        result = f"{result}\n\n{image_note}" if result else image_note
                    return "COMPLETED", result
            else:
                stable_since = None

            if now >= next_status_report:
                print(
                    f"[response wait: {int(now - start)}s] "
                    f"assistant_nodes={assistant_count}, "
                    f"generic_candidates={generic_count}, "
                    f"latest_text_chars={len(current_text)}, "
                    f"generation_active={self._is_generation_active()}, "
                    f"image_output_detected={image_output_seen}"
                )
                next_status_report = now + 10.0

            if now - start >= timeout:
                state, information = self.detect_page_state()
                if state is not None and not (
                    image_output_seen and state == "USER_ACTION_REQUIRED"
                ):
                    return state, information or ""
                diagnostic = self._response_diagnostic(current_text)
                message = (
                    f"Timed out waiting for the response to finish after {timeout:g} seconds. "
                    f"Detector diagnostics: {diagnostic}"
                )
                print(f"[response timeout] {message}")
                if current_text or image_output_seen:
                    partial = current_text.strip()
                    if image_output_seen:
                        note = (
                            "[IMAGE OUTPUT DETECTED] The image may still be generating; "
                            "check the browser."
                        )
                        partial = f"{partial}\n\n{note}" if partial else note
                    # TIMEOUT_UNKNOWN is handled by the outer CLI without printing
                    # the returned result. Display any available image-turn text
                    # here so a long-running image operation doesn't hide it.
                    if self._active_image_generation and partial:
                        print("\n[PARTIAL MODEL RESPONSE BEFORE TIMEOUT]")
                        print(partial)
                    return "TIMEOUT_UNKNOWN", f"{partial}\n\n{message}"
                return "TIMEOUT_UNKNOWN", message

            time.sleep(self.poll_interval)

    def send_prompt(self, prompt: str) -> Tuple[str, str]:
        """Send a single prompt and return ``(state, response_or_information)``.

        A prompt is never blindly inserted a second time and a clicked Send
        control is never blindly clicked again. Ambiguous outcomes return an
        error so the caller can inspect the browser without duplicating a turn.
        """
        if not isinstance(prompt, str):
            return "SEND_ERROR", "Prompt must be a string."
        if not prompt.strip():
            return "SEND_ERROR", "Prompt cannot be empty."

        # Mark the intended user turn before taking response baselines. The prompt
        # is not in the transcript yet, so the initial counts still describe only
        # existing messages; after submission, generic extraction can consistently
        # exclude the outgoing prompt rather than miscounting it as a reply.
        self._active_prompt = prompt
        self._active_image_generation = self._is_image_generation_request(prompt)
        previous_text = self.get_latest_assistant_text()
        previous_assistant_count = self._assistant_count()
        previous_generic_count = len(self._generic_message_items())
        previous_media_signature = self._generated_image_signature()
        previous_user_count = self._user_message_count()

        # STEP 1: wait for a visible editable composer.
        composer = self._wait_for_composer(self.composer_timeout)
        if composer is None:
            self._active_prompt = None
            state, information = self.detect_page_state()
            if state in {"AUTH_REQUIRED", "RATE_LIMITED", "USER_ACTION_REQUIRED"}:
                return state, information or ""
            return "NOT_READY", "No visible, editable chat composer was found."

        # STEP 2: focus the selected composer.
        try:
            composer.click(timeout=5000)
        except Exception as error:
            self._active_prompt = None
            return "SEND_ERROR", f"Could not focus the chat composer: {error}"

        # STEP 3: insert once. Playwright fill handles long prompts better than
        # simulated keystrokes and avoids waiting for per-character typing.
        print("Inserting prompt...")
        fill_error: Optional[Exception] = None
        try:
            composer.fill(prompt, timeout=10000)
        except Exception as error:
            fill_error = error

        inserted = self._wait_for_prompt_in_composer(
            prompt, timeout=min(3.0, self.insertion_timeout)
        )

        if not inserted and fill_error is not None:
            # A fill call can time out after the browser has already applied it.
            # Only fall back to one keyboard insertion if the composer is still
            # empty; never append to partial/uncertain text.
            current_composer, _score = self._find_composer_on_page(
                self.page, require_ready=False
            )
            current_text = (
                self._read_composer_text(current_composer)
                if current_composer is not None
                else ""
            )
            if current_composer is not None and not current_text.strip():
                try:
                    current_composer.click(timeout=3000)
                    self.page.keyboard.insert_text(prompt)
                except Exception as error:
                    self._active_prompt = None
                    return "SEND_ERROR", f"Could not insert prompt: {error}"
            elif current_composer is None:
                self._active_prompt = None
                return (
                    "SEND_ERROR",
                    "The composer disappeared after the fill attempt; "
                    "the prompt was not inserted again.",
                )
            else:
                self._active_prompt = None
                return (
                    "SEND_ERROR",
                    "Prompt insertion failed or timed out, and the composer is not empty. "
                    "The text was not inserted again to avoid duplication.",
                )

        print("Waiting for the complete prompt to appear in the composer...")
        if not self._wait_for_prompt_in_composer(prompt, self.insertion_timeout):
            self._active_prompt = None
            return (
                "SEND_ERROR",
                "The complete prompt could not be verified in the composer. "
                "The Send control was not clicked.",
            )

        print("Prompt inserted and verified.")

        # STEP 4: keep searching until a related Send/submit control is visible
        # and enabled. Its label or test ID is not required.
        print("Waiting for the Send control to become available...")
        send_deadline = time.monotonic() + self.send_timeout
        send_button: Optional[Locator] = None

        while time.monotonic() < send_deadline:
            composer, _score = self._find_composer_on_page(
                self.page, require_ready=False
            )
            if composer is None:
                time.sleep(self.poll_interval)
                continue
            candidate, enabled = self._find_send_button(composer)
            if candidate is not None and enabled:
                send_button = candidate
                break
            time.sleep(self.poll_interval)

        if send_button is None:
            self._active_prompt = None
            return (
                "SEND_ERROR",
                "No enabled submit control associated with the composer became available. "
                "The prompt remains in the composer and was not submitted.",
            )

        # STEP 5: click exactly once, then verify acceptance rather than retrying.
        print("Submitting prompt...")
        submission_confirmed = False
        try:
            send_button.click(timeout=10000)
        except Exception as error:
            # The click may have reached the page despite a timeout. Inspect state
            # but never click a second time automatically.
            submission_confirmed = self._wait_for_submission(
                prompt,
                previous_user_count,
                previous_text,
                previous_assistant_count,
                previous_generic_count,
            )
            if not submission_confirmed:
                self._active_prompt = None
                return (
                    "SEND_ERROR",
                    "The submit click could not be confirmed: "
                    f"{error}. The prompt was not automatically resent; check the browser.",
                )

        print("Verifying that the prompt was accepted...")
        if not submission_confirmed and not self._wait_for_submission(
            prompt,
            previous_user_count,
            previous_text,
            previous_assistant_count,
            previous_generic_count,
        ):
            self._active_prompt = None
            return (
                "SEND_ERROR",
                "The submit control was clicked, but the page did not confirm acceptance. "
                "The request was not retried to avoid sending a duplicate prompt.",
            )

        print("Submission accepted. Waiting for the model response...")
        try:
            return self.wait_for_response(
                previous_text,
                previous_assistant_count=previous_assistant_count,
                previous_generic_count=previous_generic_count,
                previous_media_signature=previous_media_signature,
            )
        finally:
            self._active_prompt = None
            self._active_image_generation = False
