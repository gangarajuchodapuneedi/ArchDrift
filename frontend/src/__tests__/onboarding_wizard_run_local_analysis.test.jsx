/**
 * Tests for OnboardingWizard "Run Local Analysis (Legacy)" feature.
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
}));

import { resolveRepo, analyzeLocalRepo } from '../api/client';

const mockResolveRepo = vi.mocked(resolveRepo);
const mockAnalyzeLocalRepo = vi.mocked(analyzeLocalRepo);

describe('OnboardingWizard Run Local Analysis (Legacy)', () => {
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
    mockAnalyzeLocalRepo.mockReset();
  });

  it('should show success message with drift count after successful analysis (keywords mode)', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock analyzeLocalRepo to return array of 2 drifts
    mockAnalyzeLocalRepo.mockResolvedValue([
      { id: 'drift-1', type: 'negative' },
      { id: 'drift-2', type: 'positive' },
    ]);

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
      expect(screen.getByText('Run Local Analysis (Legacy)')).toBeInTheDocument();
    });

    // Click "Run Local Analysis" button
    const runButton = screen.getByTestId('run-local-analysis-button');
    await user.click(runButton);

    // Wait for loading to appear
    await waitFor(() => {
      expect(screen.getByTestId('run-local-analysis-loading')).toBeInTheDocument();
    });

    // Wait for success message
    await waitFor(() => {
      const successMessage = screen.getByTestId('run-local-analysis-success');
      expect(successMessage).toBeInTheDocument();
      expect(successMessage).toHaveTextContent('Analysis complete: 2 drifts');
    });

    // Assert hint text is shown
    const hintText = screen.getByTestId('run-local-analysis-hint');
    expect(hintText).toBeInTheDocument();
    expect(hintText).toHaveTextContent('Close the wizard and open the timeline to view latest drifts.');

    // Assert error banner is not shown
    expect(screen.queryByTestId('run-local-analysis-error')).not.toBeInTheDocument();

    // Verify analyzeLocalRepo was called with correct parameters
    expect(mockAnalyzeLocalRepo).toHaveBeenCalledWith({
      repoPath: 'C:\\test\\repo',
      classifierMode: 'keywords',
      maxCommits: 50,
      maxDrifts: 5,
      configDir: undefined,
    });
  });

  it('should show error banner on analysis failure', async () => {
    // Mock resolveRepo to return a resolved repo
    mockResolveRepo.mockResolvedValue({
      repo_path: 'C:\\test\\repo',
      repo_name: 'test-repo',
    });

    // Mock analyzeLocalRepo to reject with error
    mockAnalyzeLocalRepo.mockRejectedValue(new Error('boom'));

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
      expect(screen.getByText('Run Local Analysis (Legacy)')).toBeInTheDocument();
    });

    // Click "Run Local Analysis" button
    const runButton = screen.getByTestId('run-local-analysis-button');
    await user.click(runButton);

    // Wait for error banner
    await waitFor(() => {
      const errorBanner = screen.getByTestId('run-local-analysis-error');
      expect(errorBanner).toBeInTheDocument();
      expect(errorBanner).toHaveTextContent('Analysis failed: boom');
    });

    // Assert success is not shown
    expect(screen.queryByTestId('run-local-analysis-success')).not.toBeInTheDocument();
  });

  it('should disable Run button and show note when conformance mode is selected without applied module map', async () => {
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
      expect(screen.getByText('Run Local Analysis (Legacy)')).toBeInTheDocument();
    });

    // Change mode to conformance
    const modeSelect = screen.getByTestId('local-analysis-mode');
    await user.selectOptions(modeSelect, 'conformance');

    // Wait for UI to update
    await waitFor(() => {
      const runButton = screen.getByTestId('run-local-analysis-button');
      expect(runButton).toBeDisabled();
    });

    // Assert note is shown
    const note = screen.getByTestId('local-analysis-conformance-note');
    expect(note).toBeInTheDocument();
    expect(note).toHaveTextContent('Apply module map first to enable conformance.');
  });
});

