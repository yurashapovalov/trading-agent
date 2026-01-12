13:02:27.051 Running build in Portland, USA (West) – pdx1
13:02:27.053 Build machine configuration: 2 cores, 8 GB
13:02:27.557 Retrieving list of deployment files...
13:02:27.983 Downloading 140 deployment files...
13:02:33.348 Restored build cache from previous deployment (7H5iZJn6xh5RuPi5tUAXgPDWBu1f)
13:02:34.256 Running "vercel build"
13:02:34.696 Vercel CLI 50.1.6
13:02:35.090 Installing dependencies...
13:02:36.763 
13:02:36.764 up to date in 1s
13:02:36.765 
13:02:36.765 266 packages are looking for funding
13:02:36.765   run `npm fund` for details
13:02:36.792 Detected Next.js version: 16.1.1
13:02:36.799 Running "npm run build"
13:02:36.909 
13:02:36.909 > frontend@0.1.0 build
13:02:36.910 > next build
13:02:36.910 
13:02:37.965 ▲ Next.js 16.1.1 (Turbopack)
13:02:37.967 
13:02:37.996 ⚠ The "middleware" file convention is deprecated. Please use "proxy" instead. Learn more: https://nextjs.org/docs/messages/middleware-to-proxy
13:02:38.029   Creating an optimized production build ...
13:02:58.298 ✓ Compiled successfully in 19.7s
13:02:58.300   Running TypeScript ...
13:03:06.178 Failed to compile.
13:03:06.179 
13:03:06.179 ./src/components/chat.tsx:430:19
13:03:06.179 Type error: Type 'unknown' is not assignable to type 'ReactNode'.
13:03:06.180 
13:03:06.180 [0m [90m 428 |[39m                     {step[33m.[39mmessage}
13:03:06.180  [90m 429 |[39m                   [33m<[39m[33m/[39m[33mspan[39m[33m>[39m
13:03:06.180 [31m[1m>[22m[39m[90m 430 |[39m                   {step[33m.[39mresult[33m?[39m[33m.[39mroute [33m&&[39m (
13:03:06.180  [90m     |[39m                   [31m[1m^[22m[39m
13:03:06.180  [90m 431 |[39m                     [33m<[39m[33mspan[39m className[33m=[39m[32m"text-xs bg-muted px-1.5 py-0.5 rounded"[39m[33m>[39m
13:03:06.180  [90m 432 |[39m                       {[33mString[39m(step[33m.[39mresult[33m.[39mroute)}
13:03:06.181  [90m 433 |[39m                     [33m<[39m[33m/[39m[33mspan[39m[33m>[39m[0m
13:03:06.225 Next.js build worker exited with code: 1 and signal: null
13:03:06.264 Error: Command "npm run build" exited with 1
