# Member 4 design handoff

Prepared for Mohammed Zahoor Mashahir, PES1UG24CS579, Team 8, on 3 October 2026.

## Package contents

- `SCMS_Member4_Software_Design.docx`: Section 4 for integration into the team's Software Architecture and Design Specification.
- `SCMS_Member4_Software_Design.pdf`: reviewed PDF copy of the Word document.
- Two `.puml` files: editable PlantUML sequence sources for complaint submission and appeal. Both diagrams are embedded in the Word and PDF documents; rendering these sources in PlantUML may use a different layout.

## Source baseline

Repository: https://github.com/SE-MiniProject-Team-8/Smart-Complaint-Management-System

Commit inspected: `1d2989066efba25f8c34512d351da7b83722dddf`.

Use `SRS.docx` Version 2.0 as the requirements baseline and `SCMS_Test_Plan_2.0.docx` Version 2.0 as supporting traceability. `test_scms.py` is an in-memory simulation, not an implemented Flask/SQLite interface. This package defines proposed endpoints and persistence, with no claim of implementation or executed acceptance tests.

The supplied `deliverable-2-workflow` requires at least two project-specific sequence diagrams, API definitions for at least two components, request/response/error contracts, error handling, logging/monitoring and consistency with the SRS and architecture. The package covers these items.

## Integrating with Member 3

Member 3's architecture and the official SAD template are absent from the repository. The design defines logical AuthService, ComplaintService, RoutingPolicy and SQLite Repository interfaces using the SRS's modularity requirement. Match these names to the approved component diagram before submission. If Member 3 separates audit, feedback or dashboard components, move those contracts to the corresponding component while preserving transaction and authorization rules.

Insert the document's Section 4 after Member 3's Section 3. Preserve both sequence diagrams. Adjust section numbering to the official SAD template once available; exact template-specific completeness cannot be checked without that file. Do not treat this Member 4 package as the complete team architecture/design submission.

## Decisions requiring team agreement

| Item | Source issue | Proposed design |
| --- | --- | --- |
| SLA authority | REQ-8.1 mentions Dean/Admin, but the defined user classes contain four roles and no Admin. | Use Dean with an explicit SLA_REVIEW permission. Do not introduce a fifth role through public registration. |
| SLA visibility and action | REQ-8.1 asks for all overdue complaints and REQ-8.2 asks for escalation; REQ-7.3 restricts the ordinary Dean dashboard, while REQ-4.4 restricts handler actions to current assignment. | Keep a separate minimal overdue view and a permission-scoped SLA escalation route. Confirm this exception before implementation. It gives no cross-queue resolve/reject authority. |
| SLA candidates | The SRS says time-in-current-status without explicitly excluding terminal states; the simulation excludes Resolved/Rejected. | Flag active Submitted/Escalated/Under Appeal Review records only. This is a proposed interpretation. |
| Assignment | REQ-3 defines role queues; Appendix B defines assigned_to as an optional integer handler ID. | current_level defines the queue; assigned_to may hold a named handler. Use assignment history for historic audit visibility. |
| Audit IDs | Appendix C has a malformed ID `REQ41.3` for invalid credentials. | Preserve the authoritative feature-section ID REQ-1.4, also used in Test Plan v2.0. Member 1 should correct the source RTM. |
| State and feedback rules | The SRS does not fully enumerate states or constrain repeated feedback. | Use Submitted, Escalated, Resolved, Rejected and Under Appeal Review; one feedback record per complaint; no handler actions on terminal records. Confirm these detailed rules. |
| Additional fields | SRS Appendix B omits rejected_level, version, final_review and appeal/assignment/notification entities needed by the proposed detailed design. | Add these as supporting design fields without changing functional requirement IDs. |
| Validation limits | SRS supplies many field lengths but not appeal justification, password policy or allowed category catalogue. | Propose a 1000-character appeal justification; use the SRS's free category field up to 50 characters. Have the team agree a password policy without silently inventing it as an SRS requirement. |
| Workload and retention | NFRs specify normal mini-project workload but no concurrency/data volume; retention is institution dependent. | Agree workload and retention parameters before acceptance testing and deployment. |

## Requirements covered

All 28 functional requirements REQ-1.1 through REQ-9.2, all four SEC requirements, the two security objectives, the SRS performance/data/usability/maintainability/reliability requirements, and BR-01 through BR-08 are mapped in Section 4 9. No new requirement IDs replace the team's baseline.

## Submission preparation

These are the essential Member 4 design files. Review the decisions above with Members 1 and 3, integrate the design into the SAD, and then submit the reviewed team document using your team's repository workflow. ZIP archives, separate image exports and working files are intentionally omitted.
