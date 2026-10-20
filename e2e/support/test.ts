import { test as base, expect } from '@playwright/test';
import { finalizeShots } from './evidence';

export const test = base.extend<{ _evidence: void }>({
  _evidence: [
    async ({}, use, testInfo) => {
      await use();
      finalizeShots(testInfo);
    },
    { auto: true },
  ],
});

export { expect };
