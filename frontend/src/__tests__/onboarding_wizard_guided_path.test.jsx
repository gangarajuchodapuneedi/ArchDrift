/**
 * Tests for OnboardingWizard "Guided Path" feature.
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

import { resolveRepo, suggestModuleMap, applyModuleMap } from '../api/client';

const mockResolveRepo = vi.mocked(resolveRepo);
const mockSuggestModuleMap = vi.mocked(suggestModuleMap);
const mockApplyModuleMap = vi.mocked(applyModuleMap);

describe('OnboardingWizard Guided Path', () => {
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
    mockSuggestModuleMap.mockReset();
    mockApplyModuleMap.mockReset();
    
    // Clear localStorage
    localStorage.clear();
    
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it('should be collapsed by default', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
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
      expect(screen.getByText('No Intended Architecture? (Guided Path)')).toBeInTheDocument();
    });

    // Assert summary is visible
    const summary = screen.getByTestId('guided-path-summary');
    expect(summary).toBeInTheDocument();
    expect(summary).toHaveTextContent('Use this checklist to bootstrap an intended architecture for legacy repos.');

    // Assert checklist items are not visible
    expect(screen.queryByTestId('guided-step-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('guided-step-2')).not.toBeInTheDocument();
  });

  it('should show checklist when toggle is clicked', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
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
      expect(screen.getByText('No Intended Architecture? (Guided Path)')).toBeInTheDocument();
    });

    // Click toggle button
    const toggleButton = screen.getByTestId('guided-path-toggle');
    await user.click(toggleButton);

    // Assert all 7 step containers exist
    await waitFor(() => {
      expect(screen.getByTestId('guided-step-1')).toBeInTheDocument();
      expect(screen.getByTestId('guided-step-2')).toBeInTheDocument();
      expect(screen.getByTestId('guided-step-3')).toBeInTheDocument();
      expect(screen.getByTestId('guided-step-4')).toBeInTheDocument();
      expect(screen.getByTestId('guided-step-5')).toBeInTheDocument();
      expect(screen.getByTestId('guided-step-6')).toBeInTheDocument();
      expect(screen.getByTestId('guided-step-7')).toBeInTheDocument();
    });
  });

  it('should reflect state in status chips', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock suggestModuleMap to return a result
    mockSuggestModuleMap.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      suggestion_method: 'folder_scan',
      module_map_suggestion: { version: '1.0', modules: [] },
      buckets: [],
      notes: [],
    });

    // Mock applyModuleMap to return a result
    mockApplyModuleMap.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_id: 'r1',
      config_dir: 'C:\\config',
      module_map_path: 'C:\\config\\module_map.json',
      module_map_sha256: 'abc123',
      notes: [],
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
      expect(screen.getByText('No Intended Architecture? (Guided Path)')).toBeInTheDocument();
    });

    // Click toggle to expand
    const toggleButton = screen.getByTestId('guided-path-toggle');
    await user.click(toggleButton);

    // Wait for checklist to appear
    await waitFor(() => {
      expect(screen.getByTestId('guided-step-1')).toBeInTheDocument();
    });

    // Assert step 1 is DONE (repo resolved)
    const step1Status = screen.getByTestId('guided-step-1-status');
    expect(step1Status).toHaveTextContent('DONE');

    // Suggest module map
    const suggestButton = screen.getByTestId('suggest-module-map-button');
    await user.click(suggestButton);

    await waitFor(() => {
      expect(screen.getByTestId('suggest-modules')).toBeInTheDocument();
    });

    // Apply module map
    const applyButton = screen.getByTestId('apply-module-map-button');
    await user.click(applyButton);

    await waitFor(() => {
      expect(screen.getByTestId('applied-config-dir')).toBeInTheDocument();
    });

    // Re-check statuses
    const step2Status = screen.getByTestId('guided-step-2-status');
    expect(step2Status).toHaveTextContent('DONE');

    const step3Status = screen.getByTestId('guided-step-3-status');
    expect(step3Status).toHaveTextContent('DONE');

    // Steps 4-7 should still be TODO
    const step4Status = screen.getByTestId('guided-step-4-status');
    expect(step4Status).toHaveTextContent('TODO');

    const step5Status = screen.getByTestId('guided-step-5-status');
    expect(step5Status).toHaveTextContent('TODO');

    const step6Status = screen.getByTestId('guided-step-6-status');
    expect(step6Status).toHaveTextContent('TODO');

    const step7Status = screen.getByTestId('guided-step-7-status');
    expect(step7Status).toHaveTextContent('TODO');
  });

  it('should copy checklist to clipboard', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
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
      expect(screen.getByText('No Intended Architecture? (Guided Path)')).toBeInTheDocument();
    });

    // Click toggle to expand
    const toggleButton = screen.getByTestId('guided-path-toggle');
    await user.click(toggleButton);

    // Wait for checklist to appear
    await waitFor(() => {
      expect(screen.getByTestId('guided-step-1')).toBeInTheDocument();
    });

    // Click copy button
    const copyButton = screen.getByTestId('guided-path-copy');
    await user.click(copyButton);

    // Wait for "Copied." message
    await waitFor(() => {
      const copiedMessage = screen.getByTestId('guided-path-copied');
      expect(copiedMessage).toBeInTheDocument();
      expect(copiedMessage).toHaveTextContent('Copied.');
    });

    // Assert clipboard.writeText was called
    expect(navigator.clipboard.writeText).toHaveBeenCalled();

    // Assert no error banner
    expect(screen.queryByTestId('guided-path-copy-error')).not.toBeInTheDocument();
  });
});

