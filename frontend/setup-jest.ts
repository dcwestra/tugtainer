import { COMPILER_OPTIONS, ErrorHandler, NgModule } from '@angular/core';
import { getTestBed } from '@angular/core/testing';
import {
  BrowserTestingModule,
  platformBrowserTesting,
} from '@angular/platform-browser/testing';

if (typeof globalThis.TextEncoder === 'undefined') {
  const { TextDecoder, TextEncoder } = require('util');
  globalThis.TextEncoder = TextEncoder;
  globalThis.TextDecoder = TextDecoder;
}

@NgModule({
  providers: [
    {
      provide: ErrorHandler,
      useValue: { handleError: (e: unknown) => { throw e; } },
    },
  ],
})
class TestEnvModule {}

getTestBed().initTestEnvironment(
  [BrowserTestingModule, TestEnvModule],
  platformBrowserTesting([
    { provide: COMPILER_OPTIONS, useValue: {}, multi: true },
  ]),
);
