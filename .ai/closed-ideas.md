# AI Gateway — Closed Ideas

This file records approaches we should not repeat without a strong reason.

## Do Not Use as the Core Authentication Strategy
**Idea:** Extract ChatGPT cookies, passwords, or authentication tokens from the user's normal browser profile.

**Decision:** Closed.

**Reason:** It creates unnecessary credential-handling and security risk and makes the gateway dependent on internal browser/session details.

## Do Not Build Around the Normal Chrome Profile
**Idea:** Drive the user's everyday Chrome `User Data` directory directly.

**Decision:** Closed for the current prototype.

**Reason:** Chrome's automation/debugging restrictions make the default profile a poor foundation, and a dedicated data directory is safer and easier to reason about.

## Do Not Treat a Timeout as Proof That ChatGPT Failed
**Idea:** Assume a timeout means the model did not answer.

**Decision:** Closed.

**Reason:** ChatGPT may be waiting for human interaction or may be in another UI state.

## Do Not Hard-Code One Random Preference Popup as the Entire State System
**Idea:** Make the whole gateway depend on detecting one exact text such as "Which response do you prefer?".

**Decision:** Closed.

**Reason:** The interruption is intermittent. The gateway needs broader state detection.

## Do Not Artificially Exhaust the Free Model Limit
**Idea:** Force the account to hit its free usage limit during testing.

**Decision:** Closed.

**Reason:** We can build detection based on naturally occurring UI states without intentionally consuming the user's allowance.
