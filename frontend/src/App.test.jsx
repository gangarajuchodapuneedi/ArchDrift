/**
 * Tests for App component default drift selection logic and classification utilities.
 * 
 * NOTE: This test file requires a testing framework to be set up (e.g., Vitest + React Testing Library).
 * To run these tests, install:
 *   npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom
 * 
 * Then add to package.json scripts:
 *   "test": "vitest"
 */

import { describe, it, expect } from 'vitest';
import { getPrimaryClassification, getClassificationMeta } from './components/classificationUtils';

/**
 * Helper function to find default drift ID (extracted from App.jsx for testing).
 * This matches the logic in App.jsx findDefaultDriftId function.
 */
function findDefaultDriftId(driftsList, mode) {
  if (!driftsList || driftsList.length === 0) {
    return null;
  }
  
  // Only apply violation-based selection in conformance mode
  if (mode === "conformance") {
    const violationDrift = driftsList.find((d) => {
      const forbiddenAdded = d.forbidden_edges_added_count ?? 0;
      const forbiddenRemoved = d.forbidden_edges_removed_count ?? 0;
      const cyclesAdded = d.cycles_added_count ?? 0;
      const cyclesRemoved = d.cycles_removed_count ?? 0;
      return forbiddenAdded > 0 || forbiddenRemoved > 0 || cyclesAdded > 0 || cyclesRemoved > 0;
    });
    
    if (violationDrift) {
      return violationDrift.id;
    }
  }
  
  // Fallback to first drift (current behavior)
  return driftsList[0].id;
}

describe('Default drift selection in conformance mode', () => {
  it('should select drift with violations when in conformance mode', () => {
    const drifts = [
      {
        id: 'drift-1',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
        evidence_preview: [],
      },
      {
        id: 'drift-2',
        forbidden_edges_added_count: 1,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
        evidence_preview: [{ from_module: 'ui', to_module: 'core' }],
      },
      {
        id: 'drift-3',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
        evidence_preview: [],
      },
    ];
    
    const selectedId = findDefaultDriftId(drifts, 'conformance');
    
    // Should select drift-2 (has violations) not drift-1 (first item)
    expect(selectedId).toBe('drift-2');
  });
  
  it('should fall back to first drift if no violations exist in conformance mode', () => {
    const drifts = [
      {
        id: 'drift-1',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
      {
        id: 'drift-2',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
    ];
    
    const selectedId = findDefaultDriftId(drifts, 'conformance');
    
    // Should fall back to first drift when no violations
    expect(selectedId).toBe('drift-1');
  });
  
  it('should select first drift in keywords mode regardless of violations', () => {
    const drifts = [
      {
        id: 'drift-1',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
      {
        id: 'drift-2',
        forbidden_edges_added_count: 1,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
    ];
    
    const selectedId = findDefaultDriftId(drifts, 'keywords');
    
    // In keywords mode, should always select first drift
    expect(selectedId).toBe('drift-1');
  });
  
  it('should handle cycles_added_count as violation', () => {
    const drifts = [
      {
        id: 'drift-1',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
      {
        id: 'drift-2',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 1,
        cycles_removed_count: 0,
      },
    ];
    
    const selectedId = findDefaultDriftId(drifts, 'conformance');
    
    // Should select drift-2 (has cycle violation)
    expect(selectedId).toBe('drift-2');
  });
  
  it('should handle forbidden_edges_removed_count as violation', () => {
    const drifts = [
      {
        id: 'drift-1',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 0,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
      {
        id: 'drift-2',
        forbidden_edges_added_count: 0,
        forbidden_edges_removed_count: 1,
        cycles_added_count: 0,
        cycles_removed_count: 0,
      },
    ];
    
    const selectedId = findDefaultDriftId(drifts, 'conformance');
    
    // Should select drift-2 (has forbidden_removed violation)
    expect(selectedId).toBe('drift-2');
  });
  
  it('should return null for empty drift list', () => {
    const selectedId = findDefaultDriftId([], 'conformance');
    expect(selectedId).toBeNull();
  });
});

describe('Effective classification logic', () => {
  it('should use classification when classifier_mode_used is "conformance"', () => {
    const drift = {
      id: 'test-1',
      type: 'negative',
      classification: 'no_change',
      classifier_mode_used: 'conformance',
    };
    
    const effective = getPrimaryClassification(drift);
    const meta = getClassificationMeta(drift);
    
    // Should use classification ("no_change"), not type ("negative")
    expect(effective).toBe('no_change');
    expect(meta.key).toBe('no_change');
    expect(meta.label).toBe('No Change');
    expect(meta.tone).toBe('neutral');
  });
  
  it('should use type when classifier_mode_used is not "conformance"', () => {
    const drift = {
      id: 'test-2',
      type: 'negative',
      classification: 'no_change',
      classifier_mode_used: 'keywords',
    };
    
    const effective = getPrimaryClassification(drift);
    const meta = getClassificationMeta(drift);
    
    // Should use type ("negative"), not classification ("no_change")
    expect(effective).toBe('negative');
    expect(meta.key).toBe('negative');
    expect(meta.label).toBe('Negative');
    expect(meta.tone).toBe('negative');
  });
  
  it('should use type when classifier_mode_used is missing/undefined', () => {
    const drift = {
      id: 'test-3',
      type: 'positive',
      classification: 'negative',
    };
    
    const effective = getPrimaryClassification(drift);
    const meta = getClassificationMeta(drift);
    
    // Should use type ("positive") when classifier_mode_used is not set
    expect(effective).toBe('positive');
    expect(meta.key).toBe('positive');
    expect(meta.label).toBe('Positive');
    expect(meta.tone).toBe('positive');
  });
  
  it('should fallback to "unknown" when classification is null in conformance mode', () => {
    const drift = {
      id: 'test-4',
      type: 'negative',
      classification: null,
      classifier_mode_used: 'conformance',
    };
    
    const effective = getPrimaryClassification(drift);
    const meta = getClassificationMeta(drift);
    
    // Should fallback to "unknown", not use type
    expect(effective).toBe('unknown');
    expect(meta.key).toBe('unknown');
    expect(meta.label).toBe('Unknown');
    expect(meta.tone).toBe('neutral');
  });
  
  it('should fallback to "unknown" when type is null in keywords mode', () => {
    const drift = {
      id: 'test-5',
      type: null,
      classification: 'no_change',
      classifier_mode_used: 'keywords',
    };
    
    const effective = getPrimaryClassification(drift);
    const meta = getClassificationMeta(drift);
    
    // Should fallback to "unknown", not use classification
    expect(effective).toBe('unknown');
    expect(meta.key).toBe('unknown');
    expect(meta.label).toBe('Unknown');
    expect(meta.tone).toBe('neutral');
  });
  
  it('should handle needs_review classification in conformance mode', () => {
    const drift = {
      id: 'test-6',
      type: 'negative',
      classification: 'needs_review',
      classifier_mode_used: 'conformance',
    };
    
    const effective = getPrimaryClassification(drift);
    const meta = getClassificationMeta(drift);
    
    expect(effective).toBe('needs_review');
    expect(meta.key).toBe('needs_review');
    expect(meta.label).toBe('Needs Review');
    expect(meta.tone).toBe('neutral');
  });
  
  it('should return "unknown" for null/undefined drift', () => {
    expect(getPrimaryClassification(null)).toBe('unknown');
    expect(getPrimaryClassification(undefined)).toBe('unknown');
    
    const metaNull = getClassificationMeta(null);
    expect(metaNull.key).toBe('unknown');
    expect(metaNull.label).toBe('Unknown');
    expect(metaNull.tone).toBe('neutral');
  });
});

