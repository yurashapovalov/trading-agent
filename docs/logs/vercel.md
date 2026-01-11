12:50:01.949 Running build in Portland, USA (West) – pdx1
12:50:01.949 Build machine configuration: 2 cores, 8 GB
12:50:02.060 Cloning github.com/yurashapovalov/trading-agent (Branch: main, Commit: f09dfe9)
12:50:02.626 Cloning completed: 566.000ms
12:50:03.419 Restored build cache from previous deployment (7H5iZJn6xh5RuPi5tUAXgPDWBu1f)
12:50:04.350 Running "vercel build"
12:50:04.797 Vercel CLI 50.1.6
12:50:05.097 Installing dependencies...
12:50:06.486 
12:50:06.487 up to date in 1s
12:50:06.488 
12:50:06.488 266 packages are looking for funding
12:50:06.488   run `npm fund` for details
12:50:06.519 Detected Next.js version: 16.1.1
12:50:06.525 Running "npm run build"
12:50:06.633 
12:50:06.634 > frontend@0.1.0 build
12:50:06.634 > next build
12:50:06.634 
12:50:07.702 ▲ Next.js 16.1.1 (Turbopack)
12:50:07.703 
12:50:07.711 ⚠ The "middleware" file convention is deprecated. Please use "proxy" instead. Learn more: https://nextjs.org/docs/messages/middleware-to-proxy
12:50:07.737   Creating an optimized production build ...
12:50:26.732 ✓ Compiled successfully in 18.4s
12:50:26.734   Running TypeScript ...
12:50:33.720 Failed to compile.
12:50:33.721 
12:50:33.722 ./src/components/chat.tsx:430:19
12:50:33.722 Type error: Type 'unknown' is not assignable to type 'ReactNode'.
12:50:33.722 
12:50:33.722 [0m [90m 428 |[39m                     {step[33m.[39mmessage}
12:50:33.723  [90m 429 |[39m                   [33m<[39m[33m/[39m[33mspan[39m[33m>[39m
12:50:33.723 [31m[1m>[22m[39m[90m 430 |[39m                   {step[33m.[39mresult[33m?[39m[33m.[39mroute [33m&&[39m (
12:50:33.723  [90m     |[39m                   [31m[1m^[22m[39m
12:50:33.723  [90m 431 |[39m                     [33m<[39m[33mspan[39m className[33m=[39m[32m"text-xs bg-muted px-1.5 py-0.5 rounded"[39m[33m>[39m
12:50:33.723  [90m 432 |[39m                       {[33mString[39m(step[33m.[39mresult[33m.[39mroute)}
12:50:33.723  [90m 433 |[39m                     [33m<[39m[33m/[39m[33mspan[39m[33m>[39m[0m
12:50:33.765 Next.js build worker exited with code: 1 and signal: null
12:50:33.804 Error: Command "npm run build" exited with 1