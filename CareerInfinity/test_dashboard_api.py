import asyncio
import io
import json
from datetime import date, timedelta
from unittest.mock import AsyncMock

from docx import Document
from fastapi.testclient import TestClient
import pytest

import app


def create_docx(text="Data analyst. Python SQL Excel Power BI data analysis. Education projects experience."):
    document = Document()
    document.add_paragraph(text)
    content = io.BytesIO()
    document.save(content)
    return content.getvalue()


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATABASE_PATH", str(tmp_path / "dashboard.sqlite3"))
    monkeypatch.setattr(app, "authenticated_uid", lambda _authorization: "dashboard-test-user")
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    monkeypatch.setattr(app, "_PUBLIC_JOB_FEED_CACHE", {})
    client = TestClient(app.app, raise_server_exceptions=False)
    return client


def test_dashboard_settings_market_and_skill_gap_endpoints(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    connection = app.get_database()
    profile, analysis = app.load_profile("dashboard-test-user", connection)
    profile["target_role"] = "Legacy role not in catalog"
    with connection:
        app.save_profile("dashboard-test-user", profile, analysis, connection)
    connection.close()

    summary = client.get("/dashboard/summary")
    settings = client.get("/settings")
    intelligence = client.get("/career/intelligence")
    gap = client.get("/skills/gap?role=Data%20Analyst")
    default_gap = client.get("/skills/gap")
    updated = client.patch(
        "/settings",
        json={"name": "Alex", "target_role": "Data Analyst", "preferred_location": "Hyderabad", "theme": "dark"},
    )
    saved_settings = client.get("/settings")
    updated_gap = client.get("/skills/gap")

    assert summary.status_code == 200
    assert summary.json()["analysis"] is None
    assert settings.status_code == 200
    assert intelligence.json()["market"]["is_sample"] is True
    assert intelligence.json()["market"]["roles"]
    assert intelligence.json()["market"]["roles"][0]["growth_badge"].endswith("% Growth")
    assert intelligence.json()["market"]["roles"][0]["job_count_label"].endswith("(sample)")
    assert gap.status_code == 200
    assert "SQL" in gap.json()["missing_skills"]
    assert default_gap.status_code == 200
    assert default_gap.json()["role"] == app.ROLE_MATCHER.roles[0]["title"]
    assert client.get("/skills/gap?role=Not%20A%20Role").status_code == 404
    assert updated.status_code == 200
    assert saved_settings.json()["theme"] == "dark"
    assert "Agentic AI Engineer" in saved_settings.json()["available_roles"]
    assert updated_gap.json()["role"] == "Data Analyst"
    assert updated_gap.json()["learning_path"]

    invalid_theme = client.patch("/settings", json={"theme": "system"})
    assert invalid_theme.status_code == 400


def test_career_intelligence_response_is_cached_for_repeat_visits(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    connection = app.get_database()
    profile, _ = app.load_profile("dashboard-test-user", connection)
    analysis = {
        "analyzed_at": "career-intelligence-cache-test",
        "data": {"skills": [{"name": "Python"}, {"name": "SQL"}]},
    }
    with connection:
        app.save_profile("dashboard-test-user", profile, analysis, connection)
    connection.close()
    with app._CAREER_INTELLIGENCE_CACHE_LOCK:
        app._CAREER_INTELLIGENCE_CACHE.clear()
    llm = AsyncMock(return_value={"suggestion": "Practice Python and SQL."})
    monkeypatch.setattr(app, "optional_llm_json", llm)

    first = client.get("/career/intelligence")
    second = client.get("/career/intelligence")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert llm.await_count == 1


def test_resume_upload_and_document_download_compare_delete(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)

    first = client.post(
        "/resume/analyze",
        files={"resume": ("alex.docx", create_docx(), "application/octet-stream")},
    )
    second = client.post(
        "/documents",
        files={"document": ("alex-v2.docx", create_docx("Python SQL Git APIs experience projects education."), "application/octet-stream")},
    )

    assert first.status_code == 200, first.text
    assert first.json()["analysis"]["resume_score"] > 0
    assert first.json()["role_matching"]["roles"]
    assert second.status_code == 200, second.text
    first_id, second_id = first.json()["document_id"], second.json()["id"]
    listing = client.get("/documents")
    comparison = client.get("/documents/compare", params={"first": first_id, "second": second_id})
    download = client.get(f"/documents/{first_id}/download")
    summary = client.get("/dashboard/summary")

    assert listing.status_code == 200
    assert len(listing.json()["documents"]) == 2
    resume_notice = client.get("/notifications?category=ai_insight&limit=10")
    assert resume_notice.status_code == 200
    assert any(item["notification_type"] == "resume_analysis" and not item["is_demo"] for item in resume_notice.json()["notifications"])
    assert comparison.status_code == 200
    assert len(comparison.json()["versions"]) == 2
    assert download.status_code == 200
    assert download.content.startswith(b"PK")
    assert summary.json()["document"]["id"] == second_id
    assert client.delete(f"/documents/{first_id}").status_code == 200
    assert len(client.get("/documents").json()["documents"]) == 1


def test_legacy_resume_analysis_feeds_role_and_skill_dashboards(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    analyzed = client.post(
        "/api/analyze-resume",
        files={"resume": ("alex.docx", create_docx(), "application/octet-stream")},
    )
    connection = app.get_database()
    profile, analysis = app.load_profile("dashboard-test-user", connection)
    profile["target_role"] = "Outdated target role"
    with connection:
        app.save_profile("dashboard-test-user", profile, analysis, connection)
    connection.close()
    intelligence = client.get("/career/intelligence")
    summary = client.get("/dashboard/summary")
    gap = client.get("/skills/gap?role=Data%20Analyst")
    default_gap = client.get("/skills/gap")

    assert analyzed.status_code == 200
    assert intelligence.status_code == 200
    assert intelligence.json()["role_match_source"] == "saved_analysis_skill_signals"
    assert intelligence.json()["roles"]
    assert summary.json()["best_fit_role"]
    assert summary.json()["role_match_source"] == "saved_analysis_skill_signals"
    assert "SQL" in gap.json()["matched_skills"]
    assert default_gap.json()["role"] == intelligence.json()["roles"][0]["role"]


def test_roadmap_progress_calculation_uses_completed_resources_and_study_hours():
    roadmap = {
        "stages": [
            {
                "id": "foundation",
                "title": "Foundations",
                "resources": [
                    {"id": "course-a", "estimated_hours": 4},
                    {"id": "course-b", "estimated_hours": 6},
                ],
            },
            {
                "id": "advanced",
                "title": "Advanced",
                "resources": [{"id": "course-c", "estimated_hours": 10}],
            },
        ],
    }

    progress = app.calculate_roadmap_progress(
        roadmap,
        {"course-a": {"status": "completed"}, "course-b": {"status": "in_progress"}},
        weekly_study_hours=5,
        today=date(2026, 3, 1),
    )

    assert progress["overall_percent"] == 33
    assert progress["completed_resources"] == 1
    assert progress["total_resources"] == 3
    assert progress["hours_done"] == 4
    assert progress["hours_remaining"] == 16
    assert progress["current_stage"]["stage_id"] == "foundation"
    assert progress["stages"][0]["progress_percent"] == 50
    assert progress["stages"][1]["progress_percent"] == 0
    assert progress["estimated_finish_date"] == "2026-03-23"


def test_roadmap_catalog_progress_proof_and_certificate_integration(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    summary = client.get("/dashboard/summary")
    catalog = client.get("/roadmaps")
    assert summary.json()["roadmap_progress"]["role"] == "Agentic AI Engineer"
    assert catalog.status_code == 200
    assert len(catalog.json()["roles"]) == 34
    assert sum(role["priority"] for role in catalog.json()["roles"]) == 12

    role = client.get("/roadmaps/agentic-ai-engineer/progress")
    assert role.status_code == 200
    assert role.json()["overall_percent"] == 0
    assert role.json()["current_stage"]["stage_id"] == "agentic-ai-foundations"

    first_stage = role.json()["stages"][0]
    assert first_stage["id"] == "agentic-ai-foundations"
    assert first_stage["progress"]["progress_percent"] == 0
    assert first_stage["resources"][0]["progress"]["status"] == "not_started"

    updated = client.patch(
        "/progress/agentic-ai-anthropic-course",
        json={
            "status": "completed",
            "notes": "Completed the introductory materials.",
            "proof_url": "https://example.com/credential",
        },
    )
    refreshed = client.get("/roadmaps/agentic-ai-engineer/progress")
    assert updated.status_code == 200
    assert updated.json()["verified"] is True
    assert refreshed.json()["overall_percent"] == 17
    assert refreshed.json()["verified_skills"]
    assert refreshed.json()["stages"][0]["progress"]["progress_percent"] == 50
    assert refreshed.json()["stages"][0]["resources"][0]["progress"]["verified"] is True

    uploaded = client.post(
        "/progress/agentic-ai-hf-agents/proof",
        files={"proof": ("completion.pdf", b"%PDF-1.4 test proof", "application/pdf")},
    )
    downloaded = client.get("/progress/agentic-ai-hf-agents/proof")
    assert uploaded.status_code == 200
    assert uploaded.json()["verified"] is True
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 test proof"

    monkeypatch.setattr(app, "authenticated_uid", lambda _authorization: "different-user")
    other_user_progress = client.get("/roadmaps/agentic-ai-engineer/progress")
    other_user_proof = client.get("/progress/agentic-ai-hf-agents/proof")
    assert other_user_progress.json()["overall_percent"] == 0
    assert other_user_proof.status_code == 404

    monkeypatch.setattr(app, "authenticated_uid", lambda _authorization: "dashboard-test-user")
    client.patch(
        "/progress/dataanalyst-google-cert",
        json={"status": "completed", "proof_url": "https://example.com/data-credential"},
    )
    certificates = client.get("/certificates")
    completed = next(item for item in certificates.json()["roadmap_certifications"] if item["id"] == "dataanalyst-google-cert")
    assert completed["verified"] is True
    assert completed["verify_url"] == "https://example.com/data-credential"


def test_jobs_analysis_requires_resume_and_matches_resume_skills(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    job = "Required skills: Python, SQL, Excel, Tableau and machine learning for analytics."

    missing_resume = client.post("/jobs/analyze", json={"job_description": job})
    uploaded = client.post(
        "/resume/analyze",
        files={"resume": ("alex.docx", create_docx(), "application/octet-stream")},
    )
    match = client.post("/jobs/analyze", json={"job_description": job})

    assert missing_resume.status_code == 409
    assert uploaded.status_code == 200
    assert match.status_code == 200
    assert match.json()["match_score"] > 0
    assert "Python" in match.json()["matched_skills"]
    assert "Machine Learning" in match.json()["missing_skills"]


def test_interview_session_persists_answers_and_report(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = setup_client(monkeypatch, tmp_path)
    started = client.post(
        "/interview/start",
        json={"role": "Data Analyst", "difficulty": "Beginner"},
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    answer_result = None
    for index in range(3):
        answer_result = client.post(
            f"/interview/{session_id}/answer",
            json={"answer": f"I would clarify the problem, analyze the data, test an approach, and share result {index}."},
        )
        assert answer_result.status_code == 200, answer_result.text
    report = client.get(f"/interview/{session_id}/report")

    assert answer_result.json()["completed"] is True
    assert report.status_code == 200
    assert report.json()["complete"] is True
    assert len(report.json()["answers"]) == 3


def _valid_mock_interview_questions():
    texts = [
        "How would you turn a vague role-related request into a clear plan and measurable result?",
        "Describe how you would compare two tools or methods before choosing one for a project task.",
        "What steps would you take to investigate an unexpected result and find its cause?",
        "How would you check a completed analysis or deliverable for accuracy before sharing it?",
        "Explain how you would communicate a complex finding to a teammate or stakeholder.",
    ]
    return {
        "questions": [
            {
                "text": text,
                "category": "Role knowledge",
                "expected_answer_concepts": ["clear approach", "verification"],
                "evaluation_criteria": ["Explain the steps", "Describe the checks"],
                "time_limit_seconds": 300,
                "question_type": "text",
            }
            for text in texts
        ]
    }


def _start_mock_interview(client):
    started = client.post(
        "/mock-interviews/start",
        json={"role": "Data Analyst", "experience": "Fresher", "difficulty": "Medium"},
    )
    assert started.status_code == 200, started.text
    return started.json()["id"]


def test_mock_interview_uses_labeled_samples_when_ai_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = setup_client(monkeypatch, tmp_path)
    session_id = _start_mock_interview(client)

    response = client.post(f"/mock-interviews/{session_id}/round/1")
    cached = client.post(f"/mock-interviews/{session_id}/round/1")

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "Sample questions (AI offline)"
    assert 1 <= len(response.json()["questions"]) <= 5
    assert cached.json()["provider"] == "Sample questions (AI offline)"

    connection = app.get_database()
    try:
        saved = connection.execute(
            "SELECT questions_json FROM interview_sessions WHERE id=?",
            (session_id,),
        ).fetchone()
    finally:
        connection.close()
    stored_round = json.loads(saved["questions_json"])["rounds"]["1"]
    assert stored_round["ai_generated"] is False


def test_mock_interview_retries_invalid_ai_output_once(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = setup_client(monkeypatch, tmp_path)
    session_id = _start_mock_interview(client)
    generate = AsyncMock(side_effect=[None, _valid_mock_interview_questions()])
    monkeypatch.setattr(app, "optional_llm_json", generate)

    response = client.post(f"/mock-interviews/{session_id}/round/1")

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "AI"
    assert len(response.json()["questions"]) == 5
    assert generate.await_count == 2
    assert all(call.kwargs["raise_on_error"] for call in generate.await_args_list)


def test_mock_interview_does_not_retry_provider_http_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = setup_client(monkeypatch, tmp_path)
    session_id = _start_mock_interview(client)
    generate = AsyncMock(
        side_effect=app.OptionalLLMRequestError("AI provider returned HTTP 429.", 429)
    )
    monkeypatch.setattr(app, "optional_llm_json", generate)

    response = client.post(f"/mock-interviews/{session_id}/round/1")

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "Sample questions (AI offline)"
    assert generate.await_count == 1


def test_interview_question_parser_accepts_fenced_json_and_embedded_arrays():
    fenced = app._parse_llm_json_content(
        '```json\n{"questions":[{"text":"How would you approach this task?"}]}\n```'
    )
    embedded = app._parse_llm_json_content(
        'Questions generated:\n[{"text":"How would you approach this task?"}]'
    )

    assert fenced == {"questions": [{"text": "How would you approach this task?"}]}
    assert embedded == fenced
    assert app.validate_interview_questions(
        {"questions": [{
            "text": "How would you approach this task in a clear and reliable way?",
            "category": "Role knowledge",
            "expected_answer_concepts": ["planning"],
            "evaluation_criteria": ["clear steps"],
            "time_limit_seconds": "invalid",
            "question_type": "text",
        }]},
        "Data Analyst", app.INTERVIEW_ROUNDS[0], "Medium", 1,
    ) is None


def test_optional_llm_logs_http_status_and_provider_error_body(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    request = app.httpx.Request(
        "POST", "https://api.openai.com/v1/chat/completions"
    )
    provider_response = app.httpx.Response(
        429,
        request=request,
        json={"error": {"message": "request quota exceeded"}},
    )

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return provider_response

    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(app.OptionalLLMRequestError) as error:
        asyncio.run(app.optional_llm_json("Return JSON only.", {}, raise_on_error=True))

    assert error.value.status_code == 429
    assert "HTTP 429" in caplog.text
    assert "request quota exceeded" in caplog.text


def test_drives_filters_applications_and_admin_crud(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    monkeypatch.setenv("DRIVE_ADMIN_TOKEN", "test-admin-token")
    payload = {
        "company": "Test Analytics",
        "role": "Data Analyst",
        "eligibility": "Graduates",
        "package_lpa": "To be confirmed",
        "date": (date.today() + timedelta(days=30)).isoformat(),
        "mode": "Virtual",
        "type": "Virtual",
        "required_skills": ["Python", "SQL"],
        "apply_url": "",
    }

    denied = client.post("/drives", json=payload)
    created = client.post("/drives", json=payload, headers={"X-Admin-Token": "test-admin-token"})
    assert denied.status_code == 403
    assert created.status_code == 200
    drive_id = created.json()["id"]
    drives = client.get("/drives", params={"type": "Virtual", "sort": "match"})
    application = client.post(f"/drives/{drive_id}/apply")
    updated = client.patch(
        f"/drives/{drive_id}",
        json={"eligibility": "Graduates with relevant coursework"},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    deleted = client.delete(f"/drives/{drive_id}", headers={"X-Admin-Token": "test-admin-token"})

    assert drives.status_code == 200
    assert any(item["id"] == drive_id for item in drives.json()["drives"])
    assert application.status_code == 200
    application_notice = client.get("/notifications?category=application&limit=10")
    assert any(item["notification_type"] == "placement_drive_interest" and "not confirmation" in item["message"] for item in application_notice.json()["notifications"])
    assert updated.status_code == 200
    assert deleted.status_code == 200


def test_certificates_and_feedback_are_user_scoped(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    certificates = client.get("/certificates")
    feedback = client.post("/feedback", json={"category": "Feature request", "message": "Please add weekly reminders."})
    invalid = client.post("/feedback", json={"category": "Other", "message": "bad"})

    assert certificates.status_code == 200
    assert certificates.json()["certificates"] == []
    assert certificates.json()["catalog"]
    assert feedback.status_code == 200
    assert invalid.status_code == 400


def test_notifications_pagination_filters_read_delete_and_preferences(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)

    empty = client.get("/notifications")
    connection = app.get_database()
    with connection:
        now = app.datetime.now(app.timezone.utc)
        for sequence in range(100):
            category = "internship" if sequence % 5 == 0 else "job_match" if sequence % 5 == 1 else "ai_insight"
            title = f"Test Python notification {sequence}" if sequence % 7 == 0 else f"Test notification {sequence}"
            connection.execute(
                """INSERT INTO notifications
                (id, uid, title, message, category, notification_type, is_read, created_at, is_demo)
                VALUES (?, 'dashboard-test-user', ?, 'Test fixture', ?, 'test_fixture', ?, ?, 0)""",
                (f"test-notification-{sequence}", title, category, 1 if sequence % 4 == 0 else 0, (now - timedelta(minutes=sequence)).isoformat()),
            )
    connection.close()
    first = client.get("/notifications?limit=10&offset=0")
    second = client.get("/notifications?limit=10&offset=10")
    internships = client.get("/notifications?category=internship&limit=50")
    unread = client.get("/notifications?status=unread&limit=50")
    searched = client.get("/notifications?search=Python&limit=50")

    assert empty.status_code == 200 and empty.json()["total"] == 0
    assert first.status_code == 200 and len(first.json()["notifications"]) == 10
    assert first.json()["total"] == 100 and first.json()["has_more"] is True
    assert second.status_code == 200 and len(second.json()["notifications"]) == 10
    assert not set(item["id"] for item in first.json()["notifications"]) & set(item["id"] for item in second.json()["notifications"])
    assert internships.json()["total"] == 20
    assert all(item["category"] == "internship" and not item["is_demo"] for item in internships.json()["notifications"])
    assert unread.json()["unread"] == 75
    assert searched.json()["total"] >= 1

    notification_id = unread.json()["notifications"][0]["id"]
    assert client.patch(f"/notifications/{notification_id}/read").status_code == 200
    title = unread.json()["notifications"][0]["title"]
    assert client.get("/notifications", params={"search": title}).json()["notifications"][0]["is_read"] is True
    preferences = client.patch("/notifications/preferences", json={"minimum_match_percentage": 82, "email_notifications": True})
    assert preferences.status_code == 200
    assert client.get("/notifications/preferences").json()["minimum_match_percentage"] == 82
    assert client.get("/notifications/preferences").json()["email_notifications"] is True

    monkeypatch.setattr(app, "authenticated_uid", lambda _authorization: "other-notification-user")
    assert client.get("/notifications").json()["total"] == 0
    assert client.patch(f"/notifications/{notification_id}/read").status_code == 404
    assert client.delete(f"/notifications/{notification_id}").status_code == 404
    assert client.get("/notifications/preferences").json()["email_notifications"] is False

    monkeypatch.setattr(app, "authenticated_uid", lambda _authorization: "dashboard-test-user")
    assert client.post("/notifications/read-all").json()["updated"] == 74
    assert client.get("/notifications?status=unread").json()["total"] == 0
    assert client.delete(f"/notifications/{notification_id}").status_code == 200


def test_egig_job_normalization_keeps_source_fields_and_salary_label():
    ad = {
        "id": 123, "title": "Python Developer", "posted_at": "2026-11-12T10:15:00Z",
        "url": "http://egig.in/jobs/123", "company": {"name": "Example employer", "logo": "https://images.example.org/logo.png"},
        "location": {"city": "Hyderabad", "state": "Telangana"},
        "salary": {"text": "₹5–7 LPA", "currency": "INR", "period": "year"},
        "employment_type": "Full-time", "duration": "6 months",
        "experience": "0–2 years", "eligibility": "B.Tech degree required.",
        "description": "Python and SQL role. 0-2 years experience. B.Tech degree required. Hybrid work.",
    }
    normalized = app._normalise_egig_job(ad, "Python SQL B.Tech", {}, {"preferred_roles": [], "preferred_locations": []})

    assert normalized["title"] == "Python Developer"
    assert normalized["company_name"] == "Example employer"
    assert normalized["location"] == "Hyderabad, Telangana"
    assert normalized["salary_label"] == "₹5–7 LPA"
    assert normalized["employment_type"] == "Full-time"
    assert normalized["work_mode"] == "Hybrid"
    assert normalized["duration"] == "6 months"
    assert normalized["experience"] == "0–2 years"
    assert normalized["qualification"] == "B.Tech degree required."
    assert normalized["job_url"] == "https://egig.in/jobs/123"
    assert normalized["posted_at"] == "2026-11-12T10:15:00+00:00"
    assert normalized["match_percentage"] is not None
    assert "Python" in normalized["matching_skills"]


def test_adzuna_normalization_marks_predicted_pay_as_estimated():
    ad = {
        "id": 77, "title": "Python Developer", "created": "2026-11-12T10:15:00Z",
        "redirect_url": "https://www.adzuna.in/details/77", "company": {"display_name": "Example employer"},
        "location": {"display_name": "Hyderabad, Telangana"}, "salary_min": 500000,
        "salary_max": 700000, "salary_is_predicted": "1", "contract_time": "full_time",
        "description": "Python and SQL role. 0-2 years experience. B.Tech degree required. Hybrid work.",
    }
    normalized = app._normalise_adzuna_job(ad, "Python SQL B.Tech", {}, {"preferred_roles": [], "preferred_locations": []})
    assert normalized["source"] == "Adzuna"
    assert normalized["company_name"] == "Example employer"
    assert normalized["location"] == "Hyderabad, Telangana"
    assert normalized["salary_min"] == 500000 and normalized["salary_max"] == 700000
    assert normalized["salary_label"] == "₹500,000–₹700,000 (estimated by Adzuna)"
    assert normalized["employment_type"] == "Full-time"
    assert normalized["job_url"] == "https://www.adzuna.in/details/77"
    assert normalized["posted_at"] == "2026-11-12T10:15:00+00:00"


def test_adzuna_normalization_extracts_details_embedded_in_published_description():
    ad = {
        "id": 78, "title": "SDE 3 Full Stack Engineer", "created": "2026-11-13T08:00:00Z",
        "redirect_url": "https://www.adzuna.in/details/78",
        "company": {"display_name": "Weekday AI"}, "location": {"display_name": "India"},
        "contract_time": "full_time", "salary_is_predicted": "1",
        "description": "Salary range: Rs 2700000 - Rs 4500000 (ie INR 27 - 45 LPA) Experience: 4 years Location: Bangalore JobType: full-time Eligibility: Bachelor's degree Apply by: 2026-12-01 Work mode: hybrid. Build scalable applications with JavaScript and React.",
    }
    normalized = app._normalise_adzuna_job(ad, "JavaScript React SQL", {}, {"preferred_roles": [], "preferred_locations": []})

    assert normalized["salary_label"] == "Rs 2700000 - Rs 4500000 (ie INR 27 - 45 LPA)"
    assert normalized["salary_min"] is None and normalized["salary_max"] is None
    assert normalized["experience"] == "4 years"
    assert normalized["location"] == "Bangalore"
    assert normalized["employment_type"] == "Full-time"
    assert normalized["qualification"] == "Bachelor's degree"
    assert normalized["application_deadline"] == "2026-12-01T00:00:00+00:00"
    assert normalized["work_mode"] == "Hybrid"


def test_adzuna_uses_labeled_role_package_estimate_when_listing_omits_salary():
    ad = {
        "id": 79, "title": "Senior Backend Developer", "created": "2026-11-13T08:00:00Z",
        "redirect_url": "https://www.adzuna.in/details/79", "company": {"display_name": "Example employer"},
        "location": {"display_name": "Bengaluru"}, "salary_is_predicted": "0",
        "description": "Build backend services in Python.",
    }
    normalized = app._normalise_adzuna_job(ad, "Python backend", {}, {"preferred_roles": [], "preferred_locations": []})

    assert normalized["salary_label"] == "₹4–15 LPA (project estimate)"
    assert app._estimated_package_for_role("Module Lead", "Copilot Studio AI engineering") == "₹6–18 LPA (project estimate)"


def test_adzuna_refresh_switches_from_samples_to_live_listing(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    assert client.post("/notifications/sample-jobs/seed").json()["total"] == 100
    monkeypatch.setenv("ADZUNA_APP_ID", "test-app-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test-app-key")
    monkeypatch.setenv("ADZUNA_COUNTRY", "in")
    payload = {"results": [{
        "id": 991, "title": "Python Developer", "created": "2026-11-12T10:15:00Z",
        "redirect_url": "https://www.adzuna.in/details/991", "company": {"display_name": "Live employer"},
        "location": {"display_name": "Pune, Maharashtra"}, "salary_is_predicted": "0",
        "salary_min": 500000, "salary_max": 700000, "contract_time": "full_time",
        "description": "Python and SQL role. Hybrid work.",
    }]}

    class FakeResponse:
        status_code = 200
        def json(self):
            return payload

    class FakeAsyncClient:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return False
        async def get(self, _url, **_kwargs): return FakeResponse()

    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    refreshed = client.post("/notifications/jobs/refresh")
    status = client.get("/notifications/jobs/provider-status")
    listings = client.get("/notifications?limit=50")

    assert refreshed.status_code == 200 and "Adzuna" in refreshed.json()["providers"]
    assert refreshed.json()["created"] == 1
    assert status.json() == {"provider": "Adzuna + eGig + Arbeitnow + Remotive", "providers": ["Adzuna", "eGig", "Arbeitnow", "Remotive"], "adzuna_configured": True, "app_id_present": True, "app_key_present": True}
    assert listings.json()["total"] == 1
    listing = listings.json()["notifications"][0]
    assert listing["job"]["source"] == "Adzuna"
    assert listing["job"]["salary_label"].startswith("₹500,000–₹700,000")


def test_adzuna_provider_status_never_returns_credentials(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    monkeypatch.setenv("ADZUNA_APP_ID", "private-app-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "private-app-key")
    response = client.get("/notifications/jobs/provider-status")
    assert response.status_code == 200
    assert "private-app-id" not in response.text and "private-app-key" not in response.text
    assert response.json()["adzuna_configured"] is True


def test_refresh_merges_adzuna_egig_arbeitnow_and_remotive(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATABASE_PATH", str(tmp_path / "dashboard.sqlite3"))
    monkeypatch.setattr(app, "authenticated_uid", lambda _authorization: "multi-source-user")
    monkeypatch.setattr(app, "_PUBLIC_JOB_FEED_CACHE", {})
    monkeypatch.setenv("ADZUNA_APP_ID", "test-app-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test-app-key")
    monkeypatch.setenv("ADZUNA_COUNTRY", "in")

    payloads = {
        "api.adzuna.com": {"results": [{
            "id": 701, "title": "Python Developer", "created": "2026-11-13T08:00:00Z",
            "redirect_url": "https://www.adzuna.in/details/701", "company": {"display_name": "Adzuna Labs"},
            "location": {"display_name": "Bengaluru"}, "salary_is_predicted": "0", "contract_time": "full_time",
            "description": "Python API developer with SQL experience.",
        }]},
        "egig.in": {"jobs": [{
            "id": 702, "title": "Data Analyst", "company": "eGig Labs", "location": "Hyderabad",
            "url": "https://egig.in/jobs/702", "type": "full_time", "description": "Analyze data with Python and SQL.",
        }]},
        "www.arbeitnow.com": {"data": [{
            "slug": "arbeitnow-python-703", "title": "Python Developer", "company_name": "Arbeit Labs",
            "location": "Berlin, Germany", "url": "https://www.arbeitnow.com/view/python-703", "job_types": ["full_time"],
            "created_at": 1794557700, "tags": ["Python"], "description": "Build Python services.",
        }]},
        "remotive.com": {"jobs": [{
            "id": 704, "title": "Remote Data Analyst", "company_name": "Remotive Labs",
            "candidate_required_location": "Worldwide", "url": "https://remotive.com/remote-jobs/data/analyst-704",
            "job_type": "full_time", "publication_date": "2026-11-13T08:00:00", "salary": "$70,000 - $90,000",
            "category": "Data", "description": "Analyze data with Python and SQL.",
        }]},
    }

    class FakeResponse:
        status_code = 200
        def __init__(self, body): self.body = body
        def json(self): return self.body

    class FakeAsyncClient:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return False
        async def get(self, url, **_kwargs):
            host = app.urlsplit(url).hostname
            return FakeResponse(payloads[host])

    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    result = asyncio.run(app.refresh_live_jobs(None))
    connection = app.get_database()
    try:
        sources = {row[0] for row in connection.execute("SELECT DISTINCT source FROM notification_job_details").fetchall()}
        links = {row[0] for row in connection.execute("SELECT job_url FROM notification_job_details").fetchall()}
    finally:
        connection.close()

    assert result["providers"] == ["Adzuna", "eGig", "Arbeitnow", "Remotive"]
    assert result["jobs"] == 4
    assert sources == {"Adzuna", "eGig", "Arbeitnow", "Remotive"}
    assert any(url.startswith("https://remotive.com/") for url in links)
    assert any(url.startswith("https://www.arbeitnow.com/") for url in links)


def test_egig_refresh_persists_real_listing_fields_and_deduplicates(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    payload = {"jobs": [{
        "id": 811, "title": "Python Developer Intern", "posted": "2026-11-12T10:15:00Z",
        "url": "https://egig.in/jobs/811", "company": "Test employer", "listed_by": "eGig",
        "location": "Bengaluru, Karnataka", "remote": True, "type": "Internship",
        "pay": "₹10,000–₹15,000 per month", "duration": "3 months",
    }]}

    class FakeResponse:
        status_code = 200
        def json(self):
            return payload

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return False
        async def get(self, url, **_kwargs):
            host = app.urlsplit(url).hostname
            if host == "www.arbeitnow.com":
                return FakeResponse({"data": []})
            if host == "remotive.com":
                return FakeResponse({"jobs": []})
            return FakeResponse()

    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    first = client.post("/notifications/jobs/refresh")
    second = client.post("/notifications/jobs/refresh")
    listing = client.get("/notifications?category=internship&limit=10")

    assert first.status_code == 200 and first.json()["created"] == 1
    assert second.status_code == 200 and second.json()["created"] == 0 and second.json()["updated"] == 1
    record = listing.json()["notifications"][0]
    assert record["company_name"] == "Test employer"
    assert record["job"]["source"] == "eGig"
    assert record["job"]["location"] == "Bengaluru, Karnataka"
    assert record["job"]["salary_label"] == "₹10,000–₹15,000 per month"
    assert record["job"]["job_url"] == "https://egig.in/jobs/811"
    assert record["job"]["employment_type"] == "Internship"
    assert record["job"]["work_mode"] == "Remote"
    assert record["job"]["duration"] == "3 months"
    assert record["job"]["listing_source"] == "eGig"
    assert record["job"]["salary_period"] is None


def test_egig_link_validator_rejects_external_or_script_urls():
    assert app._safe_egig_url("https://egig.in/jobs/123") == "https://egig.in/jobs/123"
    assert app._safe_egig_url("https://evil.example/jobs/123") is None
    assert app._safe_egig_url("javascript:alert(1)") is None


def test_arbeitnow_and_remotive_normalizers_preserve_source_apply_links():
    preferences = {"preferred_roles": [], "preferred_locations": []}
    arbeitnow = app._normalise_arbeitnow_job({
        "slug": "python-dev-berlin", "title": "Python Developer", "company_name": "Berlin Labs",
        "location": "Berlin, Germany", "remote": False,
        "url": "https://www.arbeitnow.com/view/python-dev-berlin", "tags": ["Python", "Django"],
        "job_types": ["full_time"], "created_at": 1794557700, "description": "Build Python APIs.",
    }, "Python Django", {}, preferences)
    remotive = app._normalise_remotive_job({
        "id": 402, "title": "Remote Python Developer", "company_name": "Remote Labs",
        "candidate_required_location": "Worldwide", "url": "https://remotive.com/remote-jobs/software-dev/remote-python-developer-402",
        "job_type": "full_time", "publication_date": "2026-11-13T08:00:00", "salary": "$70,000 - $90,000",
        "category": "Software Development", "description": "Build Python APIs.",
    }, "Python Django", {}, preferences)

    assert arbeitnow["source"] == "Arbeitnow"
    assert arbeitnow["job_url"] == "https://www.arbeitnow.com/view/python-dev-berlin"
    assert arbeitnow["employment_type"] == "Full-time"
    assert arbeitnow["posted_at"].startswith("2026-")
    assert remotive["source"] == "Remotive"
    assert remotive["job_url"].startswith("https://remotive.com/")
    assert remotive["work_mode"] == "Remote"
    assert remotive["salary_currency"] == "USD"
    assert remotive["listing_source"] == "Remotive"


def test_notification_job_schema_migrations_are_repeatable(monkeypatch, tmp_path):
    setup_client(monkeypatch, tmp_path)
    database_path = str(tmp_path / "dashboard.sqlite3")
    first = app.get_database()
    first.close()
    app._SCHEMA_PATHS.discard(database_path)

    second = app.get_database()
    columns = {row[1] for row in second.execute("PRAGMA table_info(notification_job_details)")}
    second.close()

    assert {"salary_label", "duration", "listing_source"}.issubset(columns)


def test_sample_job_notifications_seed_100_role_package_examples(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)

    seeded = client.post("/notifications/sample-jobs/seed")
    repeated = client.post("/notifications/sample-jobs/seed")
    result = client.get("/notifications?limit=50")
    second_page = client.get("/notifications?limit=50&offset=50")
    records = result.json()["notifications"] + second_page.json()["notifications"]

    assert seeded.status_code == 200
    assert seeded.json()["created"] == 100 and seeded.json()["total"] == 100
    assert repeated.json()["created"] == 0 and repeated.json()["already_seeded"] is True
    assert result.json()["total"] == 100
    assert all(item["is_demo"] and item["job"]["source"] == "Sample data" for item in records)
    assert all(item["job"]["salary_label"].endswith("(sample)") for item in records)
    assert len({item["title"].split(" ", 1)[1] for item in records}) > 10
    assert all(item["job"]["job_url"] is None and item["company_name"] is None for item in records)
