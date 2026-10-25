import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_FUELHH = [
    {
        'dataset': 'FUELHH',
        'startTime': '2026-01-15T00:00:00Z',
        'publishTime': '2026-01-15T00:35:00Z',
        'settlementDate': '2026-01-15',
        'settlementPeriod': 1,
        'fuelType': 'WIND',
        'generation': 12000.0
    },
    {
        'dataset': 'FUELHH',
        'startTime': '2026-01-15T00:30:00Z',
        'publishTime': '2026-01-15T01:05:00Z',
        'settlementDate': '2026-01-15',
        'settlementPeriod': 2,
        'fuelType': 'WIND',
        'generation': 12500.0
    }
]

SAMPLE_WINDFOR = [
    {
        'dataset': 'WINDFOR',
        'startTime': '2026-01-15T00:00:00Z',
        'publishTime': '2026-01-14T22:30:00Z',
        'generation': 13000.0
    }
]

MOCK_META = {
    'status': 'ok',
    'status_code': 200,
    'latency_ms': 45.0,
    'fetched_at': '2026-01-15T12:00:00Z',
    'record_count': 1
}


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['service'] == 'aethergrid-api'
    assert 'timestamp' in data


@patch('app.services.accuracy.fetch_fuelhh_raw', new_callable=AsyncMock)
@patch('app.services.accuracy.fetch_windfor_raw', new_callable=AsyncMock)
def test_overview_endpoint(mock_wind, mock_fuel):
    mock_fuel.return_value = (SAMPLE_FUELHH, MOCK_META)
    mock_wind.return_value = (SAMPLE_WINDFOR, MOCK_META)

    response = client.get('/api/overview?start_date=2026-01-15&end_date=2026-01-15')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'metrics' in data
    assert 'series' in data
    assert 'quality' in data
    assert data['metrics']['mae'] is not None


@patch('app.services.accuracy.fetch_fuelhh_raw', new_callable=AsyncMock)
@patch('app.services.accuracy.fetch_windfor_raw', new_callable=AsyncMock)
def test_accuracy_endpoint(mock_wind, mock_fuel):
    mock_fuel.return_value = (SAMPLE_FUELHH, MOCK_META)
    mock_wind.return_value = (SAMPLE_WINDFOR, MOCK_META)

    response = client.get('/api/accuracy?start_date=2026-01-15&end_date=2026-01-15')
    assert response.status_code == 200
    data = response.json()
    assert 'daily_summary' in data
    assert 'distribution' in data
    assert len(data['distribution']) == 6


@patch('app.services.accuracy.fetch_fuelhh_raw', new_callable=AsyncMock)
@patch('app.services.accuracy.fetch_windfor_raw', new_callable=AsyncMock)
def test_forecasts_endpoint(mock_wind, mock_fuel):
    mock_fuel.return_value = (SAMPLE_FUELHH, MOCK_META)
    mock_wind.return_value = (SAMPLE_WINDFOR, MOCK_META)

    response = client.get('/api/forecasts?date=2026-01-15')
    assert response.status_code == 200
    data = response.json()
    assert data['date'] == '2026-01-15'
    assert 'periods' in data
    assert 'cutoff_policy' in data


@patch('app.services.accuracy.fetch_fuelhh_raw', new_callable=AsyncMock)
@patch('app.services.accuracy.fetch_windfor_raw', new_callable=AsyncMock)
def test_data_quality_endpoint(mock_wind, mock_fuel):
    mock_fuel.return_value = (SAMPLE_FUELHH, MOCK_META)
    mock_wind.return_value = (SAMPLE_WINDFOR, MOCK_META)

    response = client.get('/api/data-quality?start_date=2026-01-15&end_date=2026-01-15')
    assert response.status_code == 200
    data = response.json()
    assert 'summary' in data
    assert 'integrity' in data
    assert 'upstream_connectivity' in data


def test_validation_error_on_invalid_date():
    response = client.get('/api/overview?start_date=invalid-date')
    assert response.status_code == 422


@patch('app.services.accuracy.fetch_fuelhh_raw', new_callable=AsyncMock)
def test_upstream_failure_returns_502(mock_fuel):
    mock_fuel.side_effect = Exception("Elexon upstream timeout")
    response = client.get('/api/overview?start_date=2026-01-15&end_date=2026-01-15')
    assert response.status_code == 502
    assert "Failed to evaluate wind forecast dataset" in response.json()['detail']
