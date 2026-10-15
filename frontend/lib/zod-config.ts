import { z } from "zod";

/**
 * Zod 4 checks once whether it may compile validators with `new Function` (faster parsing). Our
 * Content-Security-Policy forbids that (DECISIONS D-67), and although zod catches the refusal, Chrome still
 * reports a CSP violation in the console. `jitless` skips the check; our forms are tiny, so speed is the same.
 */
z.config({ jitless: true });
