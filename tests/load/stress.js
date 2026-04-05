/**
 * OmniGuard k6 Stress Test
 * 
 * High concurrency stress test (500+ users) with ramping pattern.
 * 
 * Usage:
 *   k6 run stress.js
 *   k6 run --out json=stress-results.json stress.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const cacheHits = new Counter('cache_hits');
const cacheMisses = new Counter('cache_misses');
const latencyTrend = new Trend('request_latency');

const BASE_URL = __ENV.BASE_URL || 'http://localhost';

export const options = {
  stages: [
    // Ramp up
    { duration: '30s', target: 100 },
    { duration: '30s', target: 250 },
    { duration: '30s', target: 500 },
    // Sustain peak
    { duration: '60s', target: 500 },
    // Ramp down
    { duration: '30s', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],  // 95% under 2s
    http_req_failed: ['rate<0.05'],      // Less than 5% errors
    errors: ['rate<0.05'],
  },
};

export default function () {
  group('API Requests', function () {
    // Mix of different endpoints
    const endpoints = [
      '/api/data',
      '/api/data?source=csv&dataset=users',
      '/api/data?endpoint=/users',
      '/health',
    ];
    
    const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
    const res = http.get(`${BASE_URL}${endpoint}`);
    
    latencyTrend.add(res.timings.duration);
    
    const success = check(res, {
      'status is 2xx': (r) => r.status >= 200 && r.status < 300,
    });
    
    errorRate.add(!success);
    
    // Track cache behavior
    if (res.headers['X-Cache'] === 'HIT') {
      cacheHits.add(1);
    } else if (res.headers['X-Cache'] === 'MISS') {
      cacheMisses.add(1);
    }
  });
  
  sleep(0.05);  // Faster iteration for stress
}

export function setup() {
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`Target not ready: ${res.status}`);
  }
  return { startTime: Date.now() };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Stress test completed in ${duration.toFixed(1)}s`);
}

export function handleSummary(data) {
  return {
    stdout: generateStressSummary(data),
    'stress-results.json': JSON.stringify(data, null, 2),
  };
}

function generateStressSummary(data) {
  const metrics = data.metrics;
  const p50 = metrics.http_req_duration?.values?.['p(50)'] || 'N/A';
  const p95 = metrics.http_req_duration?.values?.['p(95)'] || 'N/A';
  const p99 = metrics.http_req_duration?.values?.['p(99)'] || 'N/A';
  const errorPct = (metrics.http_req_failed?.values?.rate || 0) * 100;
  const rps = metrics.http_reqs?.values?.rate || 0;
  const totalReqs = metrics.http_reqs?.values?.count || 0;
  
  return `
╔═══════════════════════════════════════════════════════════════╗
║                  OMNIGUARD STRESS TEST RESULTS                ║
╠═══════════════════════════════════════════════════════════════╣
║  Peak Concurrency: 500 VUs                                    ║
║  Total Duration: ~4 minutes                                   ║
╠═══════════════════════════════════════════════════════════════╣
║  Total Requests:  ${String(totalReqs).padEnd(15)}                       ║
║  RPS (avg):       ${String(rps.toFixed(2)).padEnd(15)}req/s                  ║
╠═══════════════════════════════════════════════════════════════╣
║  P50 Latency:     ${String(p50).padEnd(15)}ms                       ║
║  P95 Latency:     ${String(p95).padEnd(15)}ms                       ║
║  P99 Latency:     ${String(p99).padEnd(15)}ms                       ║
║  Error Rate:      ${String(errorPct.toFixed(2)).padEnd(15)}%                        ║
╚═══════════════════════════════════════════════════════════════╝
`;
}
