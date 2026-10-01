# Approved scrolling implementation verification

October 1, 2026. Implements [DR-0001](../decisions/DR-0001-scrolling-conflict.md), accepted by J.L. No commit, push, deployment or live model call.

## Observed in the Demo browser

- Typed a queen-under-$550 request. The user message stayed approximately 14px below the inner chat viewport top before and after the full recommendation response. Reserved space decreased from 497px to zero as results grew.
- Selected Compare the first two. After the native animation, that new user message remained approximately 14.8px below the viewport top with the completed comparison underneath.
- Sent a short “hi” turn. The message stayed approximately 13.9px below the top, with 416px reserved trailing space after the brief answer.
- Tested manual wheel input after submitting another haul-away turn. Initial testing exposed native animation continuing after manual input; explicit wheel/touch/pointer cancellation was added. In the corrected preview, wheel movement remained near the older content (56.5px immediately, 84.5px after settling and completed response), rather than returning to the latest user message around 1330px. Response growth did not reclaim the viewport. Touch/pointer handling shares the cancellation function but was not separately device-tested.
- Selected Compare these two after manual scrolling. The new message returned to approximately 14.4px below the top. [Screenshot](evidence/2026-10-01-scrolling/user-message-at-top.png).
- Reset conversation through its menu. Observed the cold-start screen, zero user messages, scrollTop 0 and reserved space 0px.

These are browser observations and DOM measurements, not a permanent automated end-to-end suite. Native animation has intermediate positions before settling. A full-page screenshot changed capture layout and was replaced with a normal viewport screenshot; layout measurements above refer to normal browsing.

## Automated verification

The final executable changes pass 198 unit tests and all 26 deterministic Core v2 cases. [Unit log](evidence/2026-10-01-scrolling/unit.log), [evaluation log](evidence/2026-10-01-scrolling/eval.log), and [tested source hashes](evidence/2026-10-01-scrolling/summary.json). Backend unit/evaluation results are regression checks, not evidence of scrolling behavior. The frontend script also parsed successfully.

## Limits

Live backend streaming was not exercised; Demo and Live use the same reveal/submit presentation logic. Reduced-motion handling is code-inspected, not tested by changing the operating system preference. Responsive/device variations, touch scrolling, virtual keyboards, and long message/image resizing need additional coverage. No custom easing remains; content appearance animations are unchanged.
