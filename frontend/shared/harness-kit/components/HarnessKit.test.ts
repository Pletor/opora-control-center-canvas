import { describe, expect, it } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import HarnessKit from './HarnessKit';
import { harnessChanged, harnessOf } from '../logic/harness-kit';
import { specDiff } from '@/hub/oporahub-card-drawer/spec-tab/logic/spec-diff';

const fields = { goal: 'Goal', non_goals: '', acceptance: 'Checks' };
const payload = { schema: 'harness.kit/1', problems: ['ts.references'], resources: [{
  slot: 'rules.quality', resource: 'rule:quality', category: 'rules', digest: 'a'.repeat(64),
  content: 'Check the accepted requirements.', requires: ['command:npm'] }] };

describe('Harness kit review', () => {
  it('legacy absence is quiet and JSON key order does not produce a change', () => {
    expect(harnessOf(fields)).toBeNull();
    expect(renderToStaticMarkup(createElement(HarnessKit, { after: fields }))).toBe('');
    const reversed = Object.fromEntries(Object.entries(payload).reverse());
    expect(harnessChanged({ harness: payload }, { harness: reversed })).toBe(false);
  });
  it('counts addition, changed requirements and deletion even when text fields match', () => {
    const withKit = { ...fields, harness: payload };
    expect(specDiff(fields, withKit).changes).toBe(1);
    expect(specDiff(withKit, fields).changes).toBe(1);
    const changed = structuredClone(payload); changed.resources[0].requires = ['mcp:context7'];
    expect(specDiff(withKit, { ...fields, harness: changed }).changes).toBe(1);
  });
  it('renders complete content and requirements as text, including dangerous markup', () => {
    const kit = structuredClone(payload); kit.resources[0].content = '<script>alert(1)</script>';
    const html = renderToStaticMarkup(createElement(HarnessKit, { after: { harness: kit } }));
    expect(html).toContain('command:npm'); expect(html).toContain('a'.repeat(64));
    expect(html).toContain('&lt;script&gt;'); expect(html).not.toContain('<script>');
  });
  it('shows both versions and represents removal explicitly', () => {
    const html = renderToStaticMarkup(createElement(HarnessKit, { before: { harness: payload }, after: fields, mode: 'diff' }));
    expect(html).toContain('Přijatá výbava'); expect(html).toContain('Navržená výbava');
    expect(html).toContain('Bez připnuté výbavy.'); expect(html).toContain('data-oh-diff="changed"');
    const accepted = renderToStaticMarkup(createElement(HarnessKit, { before: { harness: payload }, after: fields, mode: 'accepted' }));
    expect(accepted).toContain('rule:quality');
  });
});
