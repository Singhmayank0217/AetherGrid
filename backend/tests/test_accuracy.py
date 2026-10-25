from datetime import datetime, timezone
from app.services.accuracy import select_vintages

def test_selects_latest_eligible_vintage():
    rows = [{'startTime':'2026-01-15T12:00:00Z','publishTime':'2026-01-14T20:00:00Z','generation':100},{'startTime':'2026-01-15T12:00:00Z','publishTime':'2026-01-14T21:00:00Z','generation':105},{'startTime':'2026-01-15T12:00:00Z','publishTime':'2026-01-15T01:00:00Z','generation':999}]
    assert select_vintages(rows)['2026-01-15T12:00:00+00:00']['forecast'] == 105

def test_excludes_late_publications():
    rows = [{'startTime':'2026-01-15T12:00:00Z','publishTime':'2026-01-15T23:30:00Z','generation':100}]
    assert select_vintages(rows) == {}
