import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getOverview, getAccuracy, getForecasts, getDataQuality, getHealth, getSimulator } from '../services/api';

describe('AetherGrid API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('calls getOverview with correct query parameters', async () => {
    const mockData = { status: 'ok', sample_count: 1488, metrics: { mae: 1940.8 } };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockData
    } as Response);

    const res = await getOverview('2026-01-01', '2026-01-31', 23, 'half_hourly', false);
    expect(res).toEqual(mockData);
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/overview?start_date=2026-01-01&end_date=2026-01-31&cutoff_hour=23&resolution=half_hourly&force_refresh=false')
    );
  });

  it('throws descriptive error when API returns non-200', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => ({ detail: 'Elexon stream timeout' })
    } as Response);

    await expect(getOverview('2026-01-01', '2026-01-31')).rejects.toThrow(
      'Elexon stream timeout'
    );
  });

  it('calls getForecasts for specific date', async () => {
    const mockData = { status: 'ok', date: '2026-01-15', periods: [] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockData
    } as Response);

    const res = await getForecasts('2026-01-15', 23, false);
    expect(res.date).toBe('2026-01-15');
  });

  it('calls getDataQuality report endpoint', async () => {
    const mockData = { status: 'ok', summary: { actual_record_count: 1488 } };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockData
    } as Response);

    const res = await getDataQuality('2026-01-01', '2026-01-31');
    expect(res.summary.actual_record_count).toBe(1488);
  });

  it('calls getSimulator with scenario and cutoff parameters', async () => {
    const mockData = {
      status: 'ok',
      date: '2026-01-15',
      summary: { baseline_mean_mw: 11870.8 },
      periods: []
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockData
    } as Response);

    const res = await getSimulator('2026-01-15', 11, 20.0, 500.0, 'hourly', false);
    expect(res.date).toBe('2026-01-15');
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/simulator?date=2026-01-15&cutoff_hour=11&scenario_pct=20&scenario_mw=500&resolution=hourly&force_refresh=false')
    );
  });
});
