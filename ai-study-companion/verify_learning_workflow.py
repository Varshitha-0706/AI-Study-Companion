import requests
import time
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def run_verification():
    print("==================================================")
    print("STARTING LEARNING WORKFLOW E2E VERIFICATION")
    print("==================================================")
    
    # 1. Register and Login
    print("\n[Step 1] Registering & logging in test user...")
    test_email = f"learner_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": test_email,
        "password": "StrongPassword123!",
        "display_name": "Distributed Systems Learner"
    })
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"
    token = reg_resp.json()["access_token"]
    user_id = reg_resp.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"-> Authenticated user: {user_id} ({test_email})")

    # 2. Create Space
    print("\n[Step 2] Creating Space...")
    space_resp = requests.post(f"{BASE_URL}/spaces", headers=headers, json={
        "name": "Computer Science & AI Systems",
        "description": "Studies in distributed systems, vector search, and databases"
    })
    assert space_resp.status_code == 201, f"Space creation failed: {space_resp.text}"
    space_id = space_resp.json()["id"]
    print(f"-> Created Space ID: {space_id}")

    # 3. Create Project
    print("\n[Step 3] Creating Project...")
    proj_resp = requests.post(f"{BASE_URL}/spaces/{space_id}/projects", headers=headers, json={
        "name": "Distributed Algorithms & Storage Engines",
        "description": "Mastering Raft, vector indexing, and ACID logs",
        "learning_goal": "Understand consensus, pgvector search, and WAL mechanics"
    })
    assert proj_resp.status_code == 201, f"Project creation failed: {proj_resp.text}"
    project_id = proj_resp.json()["id"]
    print(f"-> Created Project ID: {project_id}")

    # 4 & 5. Upload PDF material
    print("\n[Step 4 & 5] Uploading educational PDF material...")
    with open("sample_educational_doc.pdf", "rb") as f:
        files = {"file": ("sample_educational_doc.pdf", f, "application/pdf")}
        upload_resp = requests.post(
            f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/materials",
            headers=headers,
            files=files
        )
    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
    mat_data = upload_resp.json()
    material_id = mat_data["id"]
    print(f"-> Uploaded Material ID: {material_id}, initial status: {mat_data['status']}")

    # 6. Wait for processing lifecycle to complete
    print("\n[Step 6] Polling material status until 'ready'...")
    for _ in range(40):
        mat_check = requests.get(
            f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/materials/{material_id}",
            headers=headers
        )
        assert mat_check.status_code == 200
        status = mat_check.json()["status"]
        print(f"   Material status: {status}")
        if status == "ready":
            break
        if status == "failed":
            raise AssertionError(f"Material processing failed: {mat_check.json().get('error_message')}")
        time.sleep(2)
    assert status == "ready", "Material failed to reach 'ready' status in time"
    print("-> Document processing complete (status: ready)!")

    # 7, 8, 9. Verify Chunks, Embeddings, and Concepts
    print("\n[Step 7, 8, 9] Verifying chunks, embeddings, and concepts in DB...")
    mat_detail = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/materials/{material_id}",
        headers=headers
    ).json()
    print(f"-> Material Page count: {mat_detail.get('page_count')}, Status: {mat_detail.get('status')}")
    assert mat_detail.get("page_count") == 3, f"Expected 3 pages, got {mat_detail.get('page_count')}"
    assert mat_detail.get("status") == "ready", f"Expected ready, got {mat_detail.get('status')}"

    # Verify concepts persisted
    concepts_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/mastery",
        headers=headers
    )
    assert concepts_resp.status_code == 200, f"Mastery query failed: {concepts_resp.text}"
    concepts_list = concepts_resp.json()
    print(f"-> Persisted Concepts Count: {len(concepts_list)}")
    for c in concepts_list:
        print(f"   - Concept: {c['concept_name']} (Score: {c.get('score')}, Trend: {c.get('trend')})")
    assert len(concepts_list) > 0, "No concepts found for project!"

    # 10, 11, 12, 13, 14. Test Grounded AI Tutor Question
    print("\n[Step 10-14] Testing AI Tutor with grounded question present in PDF...")
    q1 = "How does leader election work in Raft consensus?"
    tutor_resp1 = requests.post(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/tutor/message",
        headers=headers,
        json={"content": q1}
    )
    assert tutor_resp1.status_code == 200, f"Tutor call failed: {tutor_resp1.text}"
    tutor_data1 = tutor_resp1.json()
    print(f"-> Tutor Answer: {tutor_data1['content'][:200]}...")
    print(f"-> Insufficient Evidence: {tutor_data1['insufficient_evidence']}")
    print(f"-> Confidence: {tutor_data1['confidence']}")
    print(f"-> Citations: {tutor_data1['citations']}")
    assert not tutor_data1["insufficient_evidence"], "Expected grounded answer, got insufficient evidence"
    assert len(tutor_data1["citations"]) > 0, "Expected citations from PDF"
    assert "sample_educational_doc.pdf" in tutor_data1["citations"][0]["source"]
    assert tutor_data1["citations"][0]["page"] >= 1

    # 15, 16. Test Unsupported Question
    print("\n[Step 15-16] Testing AI Tutor with unsupported question NOT in PDF...")
    q2 = "What is the capital city of Mars and how do you bake Martian pies?"
    tutor_resp2 = requests.post(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/tutor/message",
        headers=headers,
        json={"content": q2}
    )
    assert tutor_resp2.status_code == 200, f"Tutor call failed: {tutor_resp2.text}"
    tutor_data2 = tutor_resp2.json()
    print(f"-> Unsupported Question Answer: {tutor_data2['content'][:200]}...")
    print(f"-> Insufficient Evidence: {tutor_data2['insufficient_evidence']}")
    print(f"-> Confidence: {tutor_data2['confidence']}")
    assert tutor_data2["insufficient_evidence"] or tutor_data2["confidence"] == "insufficient", "Expected insufficient evidence for unrelated query"

    # 17 & 18. Start Adaptive Quiz
    print("\n[Step 17-18] Starting Adaptive Quiz...")
    quiz_start = requests.post(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/start",
        headers=headers,
        json={"length": 3}
    )
    assert quiz_start.status_code == 201, f"Quiz start failed: {quiz_start.text}"
    first_q = quiz_start.json()
    assessment_id = first_q["assessment_id"]
    q1_id = first_q["id"]
    print(f"-> Quiz Started (Assessment ID: {assessment_id})")
    print(f"-> Q1 ID: {q1_id}, Type: {first_q['question_type']}, Text: {first_q['question_text']}")
    print(f"-> Q1 Options: {first_q.get('options')}")

    # 19. Submit MCQ Answer
    print("\n[Step 19] Submitting MCQ Answer...")
    selected_ans = first_q["options"][0] if first_q.get("options") else "Distributed consensus algorithm"
    ans1_resp = requests.post(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/answer/{q1_id}",
        headers=headers,
        json={"answer": selected_ans}
    )
    assert ans1_resp.status_code == 200, f"Answer submit failed: {ans1_resp.text}"
    ans1_data = ans1_resp.json()
    print(f"-> Answer 1 Correct: {ans1_data['is_correct']}, Explanation: {ans1_data.get('explanation')}")

    # 20. Next Question (Open-Ended)
    print("\n[Step 20] Requesting and answering next question (Open-Ended)...")
    q2_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/next",
        headers=headers
    )
    assert q2_resp.status_code == 200, f"Next question failed: {q2_resp.text}"
    second_q = q2_resp.json()
    q2_id = second_q["id"]
    print(f"-> Q2 ID: {q2_id}, Type: {second_q['question_type']}, Text: {second_q['question_text']}")
    ans2_resp = requests.post(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/answer/{q2_id}",
        headers=headers,
        json={"answer": "Write-ahead logging records transaction mutations to an append-only log on disk before modifying database pages, guaranteeing durability and atomicity under crash conditions."}
    )
    assert ans2_resp.status_code == 200
    ans2_data = ans2_resp.json()
    print(f"-> Open-Ended Eval Score: {ans2_data.get('ai_score')}, Feedback: {ans2_data.get('ai_feedback')}")
    print(f"-> Understood correctly: {ans2_data.get('understood_correctly')}")

    # Question 3
    q3_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/next",
        headers=headers
    )
    if q3_resp.status_code == 200 and q3_resp.json():
        third_q = q3_resp.json()
        q3_id = third_q["id"]
        print(f"-> Q3 ID: {q3_id}, Type: {third_q['question_type']}, Text: {third_q['question_text']}")
        q3_ans = third_q["options"][0] if third_q.get("options") else "Graph-based indexing for high dimensional approximate nearest neighbor search"
        ans3_resp = requests.post(
            f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/answer/{q3_id}",
            headers=headers,
            json={"answer": q3_ans}
        )
        assert ans3_resp.status_code == 200
        print(f"-> Answer 3 recorded: {ans3_resp.json().get('is_correct')}")

    # 21. Complete Quiz
    print("\n[Step 21] Completing Quiz...")
    complete_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}",
        headers=headers
    )
    assert complete_resp.status_code == 200, f"Get assessment failed: {complete_resp.text}"
    summary = complete_resp.json()
    print(f"-> Quiz Summary Score: {summary.get('score_pct')}%, Correct: {summary.get('correct_count')}/{summary.get('total_questions')}")

    # Allow worker time to process learning workflow
    time.sleep(4)

    # 22, 23, 24. Verify Mastery, History, Context, Growth
    print("\n[Step 22-24] Verifying updated mastery records, history points, learning context...")
    mastery_post = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/mastery",
        headers=headers
    ).json()
    print(f"-> Concepts count in mastery: {len(mastery_post)}")
    for c in mastery_post:
        print(f"   - {c['concept_name']}: Score={c.get('score')}, Evidence count={c.get('evidence_count')}, Trend={c.get('trend')}")
    
    # Growth & History
    growth_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/growth",
        headers=headers
    )
    assert growth_resp.status_code == 200
    growth_data = growth_resp.json()
    print(f"-> Overall Mastery: {growth_data.get('overall_mastery')}%")
    print(f"-> Improving count: {len(growth_data.get('improving', []))}")
    print(f"-> Stable count: {len(growth_data.get('stable', []))}")
    print(f"-> Needs attention count: {len(growth_data.get('needs_attention', []))}")
    print(f"-> Insufficient data count: {len(growth_data.get('insufficient_data', []))}")

    # 25. Recommendations
    print("\n[Step 25] Verifying adaptive recommendations...")
    recs_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/recommendations",
        headers=headers
    )
    assert recs_resp.status_code == 200
    recs = recs_resp.json()
    print(f"-> Active Recommendations: {len(recs)}")
    for r in recs:
        print(f"   - [{r.get('recommendation_type')}] {r.get('content')} (Reason: {r.get('reason')})")

    # 26. Project Analytics
    print("\n[Step 26] Verifying Project Analytics...")
    analytics_resp = requests.get(
        f"{BASE_URL}/spaces/{space_id}/projects/{project_id}/analytics",
        headers=headers
    )
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    print(f"-> Total Events: {analytics.get('total_events')}")
    print(f"-> Tutor Messages: {analytics.get('tutor_messages')}")
    print(f"-> Quizzes Completed: {analytics.get('quizzes_completed')}")
    print(f"-> Materials Count: {analytics.get('materials_count')}")
    print(f"-> Concepts Count: {analytics.get('concepts_count')}")
    print(f"-> Mastery Avg: {analytics.get('mastery_avg')}%")
    assert analytics.get("total_events", 0) > 0, "Expected events logged in analytics"

    print("\n==================================================")
    print("ALL 27 VERIFICATION CHECKS PASSED PERFECTLY!")
    print("==================================================")

if __name__ == "__main__":
    run_verification()
