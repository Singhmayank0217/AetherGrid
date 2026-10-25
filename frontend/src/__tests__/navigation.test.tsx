import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MethodologyPage from '../pages/MethodologyPage';
import App from '../App';

describe('Methodology Page', () => {
  it('renders official Elexon documentation links and formulas', () => {
    render(<MethodologyPage />);

    expect(screen.getByText(/Methodology & Data Documentation/i)).toBeDefined();
    expect(screen.getByText(/Official Upstream Data Sources/i)).toBeDefined();
    expect(screen.getByText(/Day-Ahead Decision Cutoff/i)).toBeDefined();
    expect(screen.getByText(/Alignment Resolution & Settlement Period Cadence/i)).toBeDefined();
    expect(screen.getByText(/Metric Definitions & Formulas/i)).toBeDefined();

    const links = screen.getAllByRole('link', { name: /API Docs/i });
    expect(links.length).toBeGreaterThanOrEqual(2);
  });
});

describe('App Navigation and Shell', () => {
  it('renders brand mark and navigation routes', () => {
    render(
      <MemoryRouter initialEntries={['/methodology']}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getAllByText(/Aether/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Overview/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Decision Simulator/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Forecast Explorer/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Accuracy Analysis/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Data Explorer/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Methodology & Data/i).length).toBeGreaterThanOrEqual(1);
  });
});
