from decimal import Decimal

import pytest

from tests.conftest import SAMPLES

from .conftest import login


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_rejections(client):
    assert client.post("/api/auth/login", json={"email": "admin@aivanta.demo", "password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "nobody@x.io", "password": "x"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


def test_requires_authentication(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"
    r = client.get("/api/dashboard", headers={"Authorization": "Bearer garbage"})
    assert r.json()["error"]["code"] == "invalid_token"


def test_me_and_locale(client, admin):
    me = client.get("/api/auth/me", headers=admin).json()
    assert me["role"] == "admin" and "ingest" in me["permissions"]
    r = client.patch("/api/auth/me", json={"preferred_locale": "es"}, headers=admin)
    assert r.json()["preferred_locale"] == "es"
    assert client.patch("/api/auth/me", json={"preferred_locale": "fr"}, headers=admin).status_code == 422


def test_dashboard_matches_core_engine(client, admin):
    from aivanta_core import analytics as A
    from aivanta_core import serialize as S
    from aivanta_core import synthetic

    body = client.get("/api/dashboard", headers=admin).json()
    expected = S.overview_payload(synthetic.generate(days=30), A.Filters())
    assert body["overview"]["kpis"]["ai_spend"]["value"] == expected["kpis"]["ai_spend"]["value"]
    assert body["overview"]["kpis"]["roi_pct"]["value"] == expected["kpis"]["roi_pct"]["value"]
    assert body["overview"]["synthetic"] is True
    assert set(body["breakdowns"]) == {"department", "provider", "model", "use_case"}


def test_filters_and_validation(client, admin):
    r = client.get("/api/dashboard/overview?providers=openai", headers=admin).json()
    assert r["roi_applicable"] is False
    r = client.get("/api/dashboard/overview?start=2026-99-01", headers=admin)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_filters"
    assert client.get("/api/usage/breakdown/colour", headers=admin).status_code == 404


def test_use_case_endpoints(client, admin):
    rows = client.get("/api/use-cases", headers=admin).json()["rows"]
    assert {r["use_case"] for r in rows} >= {"support_triage", "invoice_matching"}
    detail = client.get("/api/use-cases/invoice_matching", headers=admin).json()
    assert detail["roi"]["status"] == "insufficient_evidence" and detail["roi"]["roi_pct"] is None
    assert client.get("/api/use-cases/nope", headers=admin).status_code == 404
    comp = client.get("/api/comparison", headers=admin).json()["rows"]
    assert all(c["decision"] in {"continue", "optimize", "selective", "experiment", "stop"} for c in comp)


def test_organization_isolation(client, admin):
    nw = login(client, "admin@northwind.demo")
    a = client.get("/api/meta", headers=admin).json()
    b = client.get("/api/meta", headers=nw).json()
    assert a["organization"] == "org_demo" and b["organization"] == "org_northwind"
    sa = client.get("/api/dashboard/overview", headers=admin).json()["kpis"]["ai_spend"]["value"]
    sb = client.get("/api/dashboard/overview", headers=nw).json()["kpis"]["ai_spend"]["value"]
    assert sa != sb
    batches = client.get("/api/ingestion/batches", headers=nw).json()["rows"]
    assert all(row["filename"] != "aivanta_usage.csv" for row in batches)


def test_rbac(client, viewer, finance, analyst):
    assert client.put("/api/assumptions", json={"values": {"min_sample_size": 40}}, headers=viewer).status_code == 403
    assert client.put("/api/assumptions", json={"values": {"min_sample_size": 40}}, headers=analyst).status_code == 403
    r = client.put("/api/assumptions", json={"values": {"min_sample_size": 40}}, headers=finance)
    assert r.status_code == 200 and r.json()["min_sample_size"] == 40
    r = client.put("/api/assumptions", json={"values": {"conservative_benefit_haircut": 3}}, headers=finance)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_assumption"
    files = {"file": ("a.csv", b"x", "text/csv")}
    assert client.post("/api/ingestion/aivanta_csv", files=files, headers=viewer).status_code == 403
    assert client.get("/api/audit", headers=finance).status_code == 403
    # restore the default so later tests compare against the default assumptions
    assert client.put("/api/assumptions", json={"values": {"min_sample_size": 30}}, headers=finance).status_code == 200


def test_ingestion_is_idempotent_and_updates_dashboard(client, analyst, admin):
    before = Decimal(str(client.get("/api/dashboard/overview", headers=admin).json()["kpis"]["ai_spend"]["value"]))
    content = (SAMPLES / "aivanta_usage.csv").read_bytes()
    r = client.post("/api/ingestion/aivanta_csv", files={"file": ("aivanta_usage.csv", content, "text/csv")},
                    headers=analyst)
    assert r.status_code == 200, r.text
    s = r.json()
    assert (s["accepted"], s["rejected"], s["duplicates"]) == (3, 2, 0)
    after = Decimal(str(client.get("/api/dashboard/overview", headers=admin).json()["kpis"]["ai_spend"]["value"]))
    assert after > before
    again = client.post("/api/ingestion/aivanta_csv", files={"file": ("aivanta_usage.csv", content, "text/csv")},
                        headers=analyst).json()
    assert (again["accepted"], again["duplicates"]) == (0, 3)
    vendor = client.post("/api/ingestion/openai",
                         files={"file": ("o.json", (SAMPLES / "openai_usage_completions.json").read_bytes())},
                         headers=analyst).json()
    assert vendor["accepted"] == 2 and vendor["unallocated"] == 1
    bad = client.post("/api/ingestion/openai", files={"file": ("x.json", b"{nope")}, headers=analyst)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "ingestion_failed"
    assert client.post("/api/ingestion/unknown", files={"file": ("x", b"1")}, headers=analyst).status_code == 404


@pytest.mark.parametrize("locale, marker", [("en", "Use case"), ("es", "Caso de uso")])
def test_reports(client, admin, locale, marker):
    r = client.get(f"/api/reports/roi.csv?locale={locale}", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert marker in r.text
    r = client.get(f"/api/reports/usage.csv?dimension=provider&locale={locale}", headers=admin)
    assert r.status_code == 200


def test_snapshots_and_audit(client, finance, admin):
    r = client.post("/api/roi-snapshots", json={"scope_type": "use_case", "scope_key": "support_triage"},
                    headers=finance)
    assert r.status_code == 200, r.text
    assert r.json()["scope_key"] == "support_triage"
    assert client.post("/api/roi-snapshots", json={"scope_type": "use_case", "scope_key": "nope"},
                       headers=finance).status_code == 404
    assert any(s["id"] == r.json()["id"] for s in client.get("/api/roi-snapshots", headers=admin).json()["rows"])
    actions = {a["action"] for a in client.get("/api/audit", headers=admin).json()["rows"]}
    assert {"create"} <= actions


def test_recommendations_and_acknowledgement(client, analyst, viewer):
    rows = client.get("/api/recommendations", headers=analyst).json()["rows"]
    assert rows
    first = rows[0]
    body = {"rule_id": first["rule_id"], "scope_type": first["scope_type"], "scope_key": first["scope_id"]}
    assert client.post("/api/alerts/acknowledge", json=body, headers=viewer).status_code == 403
    assert client.post("/api/alerts/acknowledge", json=body, headers=analyst).status_code == 200
    again = client.get("/api/recommendations", headers=analyst).json()["rows"]
    assert next(r for r in again if r["rule_id"] == first["rule_id"] and r["scope_id"] == first["scope_id"])[
        "acknowledged"] is True
