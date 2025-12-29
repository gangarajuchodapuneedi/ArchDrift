/**
 * Tests for OnboardingWizard "Effective Config" feature.
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
  getEffectiveConfig: vi.fn(),
}));

import { resolveRepo, listArchitectureSnapshots, getEffectiveConfig, analyzeLocalRepo } from '../api/client';

const mockResolveRepo = vi.mocked(resolveRepo);
const mockListArchitectureSnapshots = vi.mocked(listArchitectureSnapshots);
const mockGetEffectiveConfig = vi.mocked(getEffectiveConfig);
const mockAnalyzeLocalRepo = vi.mocked(analyzeLocalRepo);

describe('OnboardingWizard Effective Config', () => {
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
    mockGetEffectiveConfig.mockReset();
    mockAnalyzeLocalRepo.mockReset();
    
    // Clear localStorage
    localStorage.clear();
  });

  it('should resolve effective config and show success', async () => {
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
          snapshot_id: 'aaaaaaaaaaaaaaaa',
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

    // Mock getEffectiveConfig to return success
    mockGetEffectiveConfig.mockResolvedValue({
      snapshot_id: 'aaaaaaaaaaaaaaaa',
      config_dir: 'C:\\snap\\aaaaaaaaaaaaaaaa',
      module_map_sha256: 'h1',
      created_at_utc: 't1',
      repo_id: 'r1',
      repo_path: 'C:\\repo',
      module_map_path: 'x',
      snapshot_label: null,
      created_by: null,
      note: null,
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

    // Select snapshot
    const select = screen.getByTestId('snapshot-select');
    await user.selectOptions(select, 'aaaaaaaaaaaaaaaa');

    // Wait for "Effective Config" section to appear
    await waitFor(() => {
      expect(screen.getByText('Effective Config')).toBeInTheDocument();
    });

    // Click "Resolve Effective Config" button
    const resolveConfigButton = screen.getByTestId('resolve-effective-config-button');
    await user.click(resolveConfigButton);

    // Wait for loading to appear
    await waitFor(() => {
      expect(screen.getByTestId('resolve-effective-config-loading')).toBeInTheDocument();
    });

    // Wait for success display
    await waitFor(() => {
      expect(screen.queryByTestId('resolve-effective-config-loading')).not.toBeInTheDocument();
      const configDir = screen.getByTestId('effective-config-dir');
      expect(configDir).toBeInTheDocument();
      expect(configDir).toHaveTextContent('Config Dir: C:\\snap\\aaaaaaaaaaaaaaaa');
    });

    // Assert snapshot ID is shown
    const snapshotId = screen.getByTestId('effective-snapshot-id');
    expect(snapshotId).toBeInTheDocument();
    expect(snapshotId).toHaveTextContent('Snapshot ID: aaaaaaaaaaaaaaaa');
  });

  it('should use effectiveConfigDir for conformance run when appliedConfigDir is missing', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock listArchitectureSnapshots
    mockListArchitectureSnapshots.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_id: 'r1',
      snapshots: [
        {
          snapshot_id: 'aaaaaaaaaaaaaaaa',
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

    // Mock getEffectiveConfig
    mockGetEffectiveConfig.mockResolvedValue({
      snapshot_id: 'aaaaaaaaaaaaaaaa',
      config_dir: 'C:\\snap\\aaaaaaaaaaaaaaaa',
      module_map_sha256: 'h1',
      created_at_utc: 't1',
      repo_id: 'r1',
      repo_path: 'C:\\repo',
      module_map_path: 'x',
      snapshot_label: null,
      created_by: null,
      note: null,
    });

    // Mock analyzeLocalRepo
    mockAnalyzeLocalRepo.mockResolvedValue([]);

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

    // Load and select snapshot
    const loadButton = screen.getByTestId('load-snapshots-button');
    await user.click(loadButton);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-select')).toBeInTheDocument();
    });

    const select = screen.getByTestId('snapshot-select');
    await user.selectOptions(select, 'aaaaaaaaaaaaaaaa');

    // Resolve effective config
    await waitFor(() => {
      expect(screen.getByText('Effective Config')).toBeInTheDocument();
    });

    const resolveConfigButton = screen.getByTestId('resolve-effective-config-button');
    await user.click(resolveConfigButton);

    await waitFor(() => {
      expect(screen.getByTestId('effective-config-dir')).toBeInTheDocument();
    });

    // Switch to conformance mode
    const modeSelect = screen.getByTestId('local-analysis-mode');
    await user.selectOptions(modeSelect, 'conformance');

    // Verify button is enabled (not disabled)
    const runButton = screen.getByTestId('run-local-analysis-button');
    expect(runButton).not.toBeDisabled();

    // Click run
    await user.click(runButton);

    // Wait for analyzeLocalRepo to be called
    await waitFor(() => {
      expect(mockAnalyzeLocalRepo).toHaveBeenCalled();
    });

    // Assert analyzeLocalRepo was called with effectiveConfigDir
    const callArgs = mockAnalyzeLocalRepo.mock.calls[0][0];
    expect(callArgs.configDir).toBe('C:\\snap\\aaaaaaaaaaaaaaaa');
    expect(callArgs.classifierMode).toBe('conformance');
  });

  it('should show error banner on failure', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock listArchitectureSnapshots
    mockListArchitectureSnapshots.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_id: 'r1',
      snapshots: [
        {
          snapshot_id: 'aaaaaaaaaaaaaaaa',
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

    // Mock getEffectiveConfig to reject with error
    mockGetEffectiveConfig.mockRejectedValue(new Error('boom'));

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

    // Load and select snapshot
    const loadButton = screen.getByTestId('load-snapshots-button');
    await user.click(loadButton);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-select')).toBeInTheDocument();
    });

    const select = screen.getByTestId('snapshot-select');
    await user.selectOptions(select, 'aaaaaaaaaaaaaaaa');

    // Resolve effective config
    await waitFor(() => {
      expect(screen.getByText('Effective Config')).toBeInTheDocument();
    });

    const resolveConfigButton = screen.getByTestId('resolve-effective-config-button');
    await user.click(resolveConfigButton);

    // Wait for error banner
    await waitFor(() => {
      const errorBanner = screen.getByTestId('resolve-effective-config-error');
      expect(errorBanner).toBeInTheDocument();
      expect(errorBanner).toHaveTextContent('Resolve failed: boom');
      expect(errorBanner).toHaveAttribute('role', 'alert');
    });
  });
});

