/**
 * Tests for OnboardingWizard "Snapshot Picker" feature.
 * 
 * NOTE: This test file requires React Testing Library to be installed:
 *   npm install --save-dev @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OnboardingWizard from '../components/OnboardingWizard';

// Mock the API client
vi.mock('../api/client', () => ({
  resolveRepo: vi.fn(),
  fetchBaselineStatus: vi.fn(),
  generateBaseline: vi.fn(),
  approveBaseline: vi.fn(),
  suggestModuleMap: vi.fn(),
  applyModuleMap: vi.fn(),
  analyzeLocalRepo: vi.fn(),
  createArchitectureSnapshot: vi.fn(),
  listArchitectureSnapshots: vi.fn(),
}));

import { resolveRepo, listArchitectureSnapshots } from '../api/client';

const mockResolveRepo = vi.mocked(resolveRepo);
const mockListArchitectureSnapshots = vi.mocked(listArchitectureSnapshots);

describe('OnboardingWizard Snapshot Picker', () => {
  let mockOnClose;
  let mockOnActiveRepoUpdated;
  let user;

  beforeEach(() => {
    user = userEvent.setup();
    mockOnClose = vi.fn();
    mockOnActiveRepoUpdated = vi.fn();
    
    // Reset all mocks
    vi.clearAllMocks();
    mockResolveRepo.mockReset();
    mockListArchitectureSnapshots.mockReset();
    
    // Clear localStorage
    localStorage.clear();
  });

  it('should load snapshots and show dropdown', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock listArchitectureSnapshots to return snapshots
    mockListArchitectureSnapshots.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_id: 'r1',
      snapshots: [
        {
          snapshot_id: 's1',
          created_at_utc: '2025-01-01T00:00:00Z',
          snapshot_label: 'v1',
          created_by: 't',
          note: 'n',
          module_map_sha256: 'h',
          rules_hash: null,
          baseline_hash: null,
        },
      ],
    });

    render(<OnboardingWizard onClose={mockOnClose} onActiveRepoUpdated={mockOnActiveRepoUpdated} />);

    // Step 1: Enter repo URL
    const repoInput = screen.getByTestId('repo-url-input');
    await user.type(repoInput, 'C:\\test\\repo');

    // Step 2: Click resolve button
    const resolveButton = screen.getByTestId('resolve-repo-button');
    await user.click(resolveButton);

    // Wait for resolve to complete
    await waitFor(() => {
      expect(screen.getByTestId('resolved-repo-path')).toBeInTheDocument();
    });

    // Navigate to Step 3
    const nextButton = screen.getByTestId('wizard-next');
    await user.click(nextButton);
    await user.click(nextButton);

    // Wait for Step 3 to load
    await waitFor(() => {
      expect(screen.getByText('Select Snapshot')).toBeInTheDocument();
    });

    // Click "Load Snapshots" button
    const loadButton = screen.getByTestId('load-snapshots-button');
    await user.click(loadButton);

    // Wait for loading to appear
    await waitFor(() => {
      expect(screen.getByTestId('load-snapshots-loading')).toBeInTheDocument();
    });

    // Wait for loading to disappear and dropdown to appear
    await waitFor(() => {
      expect(screen.queryByTestId('load-snapshots-loading')).not.toBeInTheDocument();
      expect(screen.getByTestId('snapshot-select')).toBeInTheDocument();
    });

    // Assert dropdown exists and includes option
    const select = screen.getByTestId('snapshot-select');
    expect(select).toBeInTheDocument();
    expect(screen.getByText('v1 — 2025-01-01T00:00:00Z')).toBeInTheDocument();

    // Select "s1"
    await user.selectOptions(select, 's1');

    // Wait for details to appear
    await waitFor(() => {
      const details = screen.getByTestId('snapshot-details');
      expect(details).toBeInTheDocument();
      expect(details).toHaveTextContent('s1');
    });
  });

  it('should persist selection to localStorage', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock listArchitectureSnapshots to return snapshots
    mockListArchitectureSnapshots.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_id: 'r1',
      snapshots: [
        {
          snapshot_id: 's1',
          created_at_utc: '2025-01-01T00:00:00Z',
          snapshot_label: 'v1',
          created_by: 't',
          note: 'n',
          module_map_sha256: 'h',
          rules_hash: null,
          baseline_hash: null,
        },
      ],
    });

    render(<OnboardingWizard onClose={mockOnClose} onActiveRepoUpdated={mockOnActiveRepoUpdated} />);

    // Step 1: Enter repo URL
    const repoInput = screen.getByTestId('repo-url-input');
    await user.type(repoInput, 'C:\\test\\repo');

    // Step 2: Click resolve button
    const resolveButton = screen.getByTestId('resolve-repo-button');
    await user.click(resolveButton);

    // Wait for resolve to complete
    await waitFor(() => {
      expect(screen.getByTestId('resolved-repo-path')).toBeInTheDocument();
    });

    // Navigate to Step 3
    const nextButton = screen.getByTestId('wizard-next');
    await user.click(nextButton);
    await user.click(nextButton);

    // Wait for Step 3 to load
    await waitFor(() => {
      expect(screen.getByText('Select Snapshot')).toBeInTheDocument();
    });

    // Click "Load Snapshots" button
    const loadButton = screen.getByTestId('load-snapshots-button');
    await user.click(loadButton);

    // Wait for dropdown to appear
    await waitFor(() => {
      expect(screen.getByTestId('snapshot-select')).toBeInTheDocument();
    });

    // Select "s1"
    const select = screen.getByTestId('snapshot-select');
    await user.selectOptions(select, 's1');

    // Assert localStorage key is set
    await waitFor(() => {
      expect(localStorage.getItem('archdrift.onboarding.snapshotId')).toBe('s1');
    });

    // Select "(none)"
    await user.selectOptions(select, '');

    // Assert localStorage key is removed
    await waitFor(() => {
      expect(localStorage.getItem('archdrift.onboarding.snapshotId')).toBeNull();
    });
  });

  it('should show error banner on failure', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock listArchitectureSnapshots to reject with error
    mockListArchitectureSnapshots.mockRejectedValue(new Error('boom'));

    render(<OnboardingWizard onClose={mockOnClose} onActiveRepoUpdated={mockOnActiveRepoUpdated} />);

    // Step 1: Enter repo URL
    const repoInput = screen.getByTestId('repo-url-input');
    await user.type(repoInput, 'C:\\test\\repo');

    // Step 2: Click resolve button
    const resolveButton = screen.getByTestId('resolve-repo-button');
    await user.click(resolveButton);

    // Wait for resolve to complete
    await waitFor(() => {
      expect(screen.getByTestId('resolved-repo-path')).toBeInTheDocument();
    });

    // Navigate to Step 3
    const nextButton = screen.getByTestId('wizard-next');
    await user.click(nextButton);
    await user.click(nextButton);

    // Wait for Step 3 to load
    await waitFor(() => {
      expect(screen.getByText('Select Snapshot')).toBeInTheDocument();
    });

    // Click "Load Snapshots" button
    const loadButton = screen.getByTestId('load-snapshots-button');
    await user.click(loadButton);

    // Wait for error banner
    await waitFor(() => {
      const errorBanner = screen.getByTestId('load-snapshots-error');
      expect(errorBanner).toBeInTheDocument();
      expect(errorBanner).toHaveTextContent('Load failed: boom');
    });

    // Assert dropdown is not shown
    expect(screen.queryByTestId('snapshot-select')).not.toBeInTheDocument();
  });
});

