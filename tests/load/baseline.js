/**
 * OmniGuard k6 Baseline Load Test
 * 
 * Quick baseline test for 50 concurrent users.
 * 
 * Usage:
 *   k6 run baseline.js
 *   k6 run --out json=results.json baseline.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');
const BASE_URL = __ENV.BASE_URL || 'http://localhost';

export const options = {
  vus: 50,
  duration: '60s',
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests under 500ms
    http_req_failed: ['rate<0.01'],     // Less than 1% errors
    errors: ['rate<0.01'],
  },
};

export default function () {
  // Primary endpoint test
  const res = http.get(`${BASE_URL}/api/data`);
  
  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'has X-Cache header': (r) => r.headers['X-Cache'] !== undefined,
    'latency < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  
  sleep(0.1);
}

export function handleSummary(data) {
  return {
    stdout: generateTextSummary(data),
    'baseline-results.json': JSON.stringify(data, null, 2),
  };
}

function generateTextSummary(data) {
  const metrics = data.metrics;
  const p95 = metrics.http_req_duration?.values?.['p(95)'] || 'N/A';
  const errorPct = (metrics.http_req_failed?.values?.rate || 0) * 100;
  const rps = metrics.http_reqs?.values?.rate || 0;
  
  return `
╔═══════════════════════════════════════════════════════════════╗
║                 OMNIGUARD BASELINE RESULTS                    ║
╠═══════════════════════════════════════════════════════════════╣
║  Concurrency: 50 VUs                                          ║
║  Duration: 60s                                                ║
╠═══════════════════════════════════════════════════════════════╣
║  P95 Latency: ${String(p95).padEnd(10)}ms                               ║
║  Error Rate:  ${String(errorPct.toFixed(2)).padEnd(10)}%                               ║
║  RPS:         ${String(rps.toFixed(2)).padEnd(10)}req/s                           ║
╚═══════════════════════════════════════════════════════════════╝
`;
}
