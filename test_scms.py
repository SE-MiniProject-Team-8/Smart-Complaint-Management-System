import unittest
from datetime import datetime, timedelta

# --- Simulated SCMS Domain Logic & Application State ---

class SCMSCore:
    def __init__(self):
        self.users = {}
        self.complaints = {}
        self.audit_logs = []
        self.feedback = []
        self.complaint_counter = 100
        self.audit_counter = 1

    def register_user(self, user_id, name, email, password, role="Student"):
        if not user_id or not name or not email or not password:
            raise ValueError("All fields are mandatory.")
        # SEC-01: Hash storage simulation
        password_hash = f"pbkdf2_sha256${hash(password)}"
        self.users[user_id] = {
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role": role
        }
        return True

    def login(self, user_id, password):
        # SEC-04 / REQ-1.4: Generic authentication rejection
        user = self.users.get(user_id)
        if not user:
            return False, "Invalid credentials."
        expected_hash = f"pbkdf2_sha256${hash(password)}"
        if user["password_hash"] != expected_hash:
            return False, "Invalid credentials."
        return True, "Login successful."

    def submit_complaint(self, student_id, category, description, severity):
        # REQ-2.2: Input validation
        if not category or not description:
            raise ValueError("Category and Description are mandatory.")
        if severity not in ["Low", "Medium", "High"]:
            raise ValueError("Severity must be Low, Medium, or High.")

        self.complaint_counter += 1
        cid = f"C-{self.complaint_counter}"

        # REQ-3.1 & REQ-3.2: Severity routing
        if severity in ["Low", "Medium"]:
            assigned_to = "Faculty-in-Charge"
            level = 1
        else:
            assigned_to = "Grievance Committee"
            level = 2

        now = datetime.now()
        complaint = {
            "complaint_id": cid,
            "student_id": student_id,
            "category": category,
            "description": description,
            "severity": severity,
            "status": "Submitted",
            "current_level": level,
            "assigned_to": assigned_to,
            "submitted_at": now,
            "status_updated_at": now,
            "appealed": False,
            "rejection_reason": None,
            "resolution_remarks": None
        }
        self.complaints[cid] = complaint

        # REQ-6.1: Immutable audit entry
        self._add_audit(cid, student_id, "SUBMIT", "None", "Submitted")
        return cid

    def resolve_complaint(self, complaint_id, actor_id, actor_role, remarks):
        # REQ-4.1 & REQ-4.4: Handler authorization and remarks check
        complaint = self.complaints.get(complaint_id)
        if complaint["assigned_to"] != actor_role:
            raise PermissionError("Access denied: Not assigned to your role.")
        if not remarks or remarks.strip() == "":
            raise ValueError("Resolution remarks are mandatory.")

        prev_status = complaint["status"]
        complaint["status"] = "Resolved"
        complaint["resolution_remarks"] = remarks
        complaint["status_updated_at"] = datetime.now()
        self._add_audit(complaint_id, actor_id, "RESOLVE", prev_status, "Resolved")

    def escalate_complaint(self, complaint_id, actor_id, actor_role):
        # REQ-4.3: Escalation boundary
        complaint = self.complaints.get(complaint_id)
        if complaint["current_level"] >= 3 or complaint["assigned_to"] == "Dean":
            raise ValueError("Escalation ceiling reached. Dean cannot escalate further.")

        prev_status = complaint["status"]
        if complaint["current_level"] == 1:
            complaint["current_level"] = 2
            complaint["assigned_to"] = "Grievance Committee"
        elif complaint["current_level"] == 2:
            complaint["current_level"] = 3
            complaint["assigned_to"] = "Dean"

        complaint["status"] = "Escalated"
        complaint["status_updated_at"] = datetime.now()
        self._add_audit(complaint_id, actor_id, "ESCALATE", prev_status, "Escalated")

    def appeal_complaint(self, complaint_id, student_id, justification):
        # REQ-5.1 & REQ-5.3: Single appeal check on rejected items
        complaint = self.complaints.get(complaint_id)
        if complaint["student_id"] != student_id:
            raise PermissionError("Only the submitting student may appeal.")
        if complaint["status"] != "Rejected":
            raise ValueError("Only Rejected complaints can be appealed.")
        if complaint["appealed"]:
            raise ValueError("Only one appeal is permitted per complaint.")

        prev_status = complaint["status"]
        complaint["appealed"] = True
        complaint["status"] = "Under Appeal Review"
        # Reassign one level higher (capped at Dean)
        if complaint["current_level"] == 1:
            complaint["current_level"] = 2
            complaint["assigned_to"] = "Grievance Committee"
        else:
            complaint["current_level"] = 3
            complaint["assigned_to"] = "Dean"

        complaint["status_updated_at"] = datetime.now()
        self._add_audit(complaint_id, student_id, "APPEAL", prev_status, "Under Appeal Review")

    def evaluate_sla_overdue(self, threshold_days=7):
        # REQ-8.1: Overdue evaluation
        overdue_list = []
        now = datetime.now()
        for cid, comp in self.complaints.items():
            if comp["status"] not in ["Resolved", "Rejected"]:
                age_days = (now - comp["status_updated_at"]).total_seconds() / 86400
                if age_days > threshold_days:
                    overdue_list.append({
                        "complaint_id": cid,
                        "current_handler": comp["assigned_to"],
                        "days_overdue": int(age_days - threshold_days)
                    })
        return overdue_list

    def submit_feedback(self, complaint_id, rating, comment=""):
        # REQ-9.1: Feedback rating validation
        complaint = self.complaints.get(complaint_id)
        if not complaint or complaint["status"] != "Resolved":
            raise ValueError("Feedback can only be submitted for Resolved complaints.")
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValueError("Rating must be an integer between 1 and 5.")

        self.feedback.append({
            "complaint_id": complaint_id,
            "rating": rating,
            "comment": comment
        })

    def _add_audit(self, complaint_id, actor_id, action, prev_status, new_status):
        self.audit_counter += 1
        self.audit_logs.append({
            "audit_id": f"A-{self.audit_counter}",
            "complaint_id": complaint_id,
            "actor_id": actor_id,
            "action": action,
            "previous_status": prev_status,
            "new_status": new_status,
            "timestamp": datetime.now()
        })


# --- Executable Unit and Integration Tests ---

class TestSCMSDeliverable(unittest.TestCase):
    def setUp(self):
        self.sys = SCMSCore()
        # Seed test accounts
        self.sys.register_user("STU001", "Alice Student", "alice@univ.edu", "Stu@1234", "Student")
        self.sys.register_user("FAC001", "Prof. Bob", "bob@univ.edu", "Fac@1234", "Faculty-in-Charge")
        self.sys.register_user("DEAN01", "Dean Davis", "dean@univ.edu", "Dean@1234", "Dean")

    # UT_1_01: Verify valid registration
    def test_ut_1_01_valid_registration(self):
        result = self.sys.register_user("STU002", "Charlie", "charlie@univ.edu", "Pass@123")
        self.assertTrue(result)
        self.assertIn("STU002", self.sys.users)

    # UT_1_03: Generic auth failure message
    def test_ut_1_03_invalid_credentials_generic_message(self):
        success, msg = self.sys.login("STU001", "WrongPassword")
        self.assertFalse(success)
        self.assertEqual(msg, "Invalid credentials.")

    # UT_2_02: Mandatory category validation
    def test_ut_2_02_mandatory_fields_rejection(self):
        with self.assertRaises(ValueError):
            self.sys.submit_complaint("STU001", category="", description="Water issue", severity="Low")

    # UT_3_01 & UT_3_03: Severity auto-routing
    def test_ut_3_routing_logic(self):
        cid_low = self.sys.submit_complaint("STU001", "Facilities", "AC broken", "Low")
        self.assertEqual(self.sys.complaints[cid_low]["assigned_to"], "Faculty-in-Charge")

        cid_high = self.sys.submit_complaint("STU001", "Exam", "Grade discrepancy", "High")
        self.assertEqual(self.sys.complaints[cid_high]["assigned_to"], "Grievance Committee")

    # UT_4_01: Resolve action requires remarks
    def test_ut_4_01_resolve_remarks_mandatory(self):
        cid = self.sys.submit_complaint("STU001", "Facilities", "Fan issue", "Low")
        with self.assertRaises(ValueError):
            self.sys.resolve_complaint(cid, "FAC001", "Faculty-in-Charge", remarks="")

    # UT_4_03: Disallow escalation beyond Dean
    def test_ut_4_03_escalation_ceiling(self):
        cid = self.sys.submit_complaint("STU001", "Admin", "Fee error", "High")
        self.sys.escalate_complaint(cid, "GC001", "Grievance Committee")
        self.assertEqual(self.sys.complaints[cid]["assigned_to"], "Dean")
        
        with self.assertRaises(ValueError):
            self.sys.escalate_complaint(cid, "DEAN01", "Dean")

    # UT_5_02: Disallow duplicate appeal
    def test_ut_5_02_prevent_second_appeal(self):
        cid = self.sys.submit_complaint("STU001", "Lab", "Access card issue", "Low")
        self.sys.complaints[cid]["status"] = "Rejected"
        
        self.sys.appeal_complaint(cid, "STU001", "Please reconsider.")
        self.assertEqual(self.sys.complaints[cid]["status"], "Under Appeal Review")
        
        # Second appeal attempt must be blocked
        with self.assertRaises(ValueError):
            self.sys.appeal_complaint(cid, "STU001", "Second appeal attempt.")

    # IT_6_01: Verify audit log generation
    def test_it_6_01_audit_log_generation(self):
        initial_log_count = len(self.sys.audit_logs)
        cid = self.sys.submit_complaint("STU001", "Hostel", "Room key missing", "Low")
        self.assertEqual(len(self.sys.audit_logs), initial_log_count + 1)
        self.assertEqual(self.sys.audit_logs[-1]["action"], "SUBMIT")
        self.assertEqual(self.sys.audit_logs[-1]["complaint_id"], cid)

    # UT_8_01 & UT_8_02: SLA overdue flagging
    def test_ut_8_sla_overdue_flagging(self):
        cid = self.sys.submit_complaint("STU001", "Library", "Book fine issue", "Low")
        # Backdate the status update time to simulate an 8-day-old complaint
        self.sys.complaints[cid]["status_updated_at"] = datetime.now() - timedelta(days=8)
        
        overdue = self.sys.evaluate_sla_overdue(threshold_days=7)
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["complaint_id"], cid)

    # UT_9_01: Feedback score validation
    def test_ut_9_01_feedback_score_validation(self):
        cid = self.sys.submit_complaint("STU001", "Wi-Fi", "Slow speed", "Low")
        self.sys.resolve_complaint(cid, "FAC001", "Faculty-in-Charge", remarks="AP restarted.")
        
        # Rating out of bounds (<1 or >5)
        with self.assertRaises(ValueError):
            self.sys.submit_feedback(cid, rating=6, comment="Superb")
            
        self.sys.submit_feedback(cid, rating=5, comment="Resolved quickly")
        self.assertEqual(len(self.sys.feedback), 1)
        self.assertEqual(self.sys.feedback[0]["rating"], 5)


if __name__ == "__main__":
    unittest.main()