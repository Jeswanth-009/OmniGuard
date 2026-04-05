/**
 * OmniGuard k6 Load Test Suite
 * 
 * Reproducible load scripts for capacity testing with configurable concurrency.
 * 
 * Usage:
 *   # 50 concurrent users
 *   k6 run --vus 50 --duration 60s load-test.js
 * 
 *   # 200 concurrent users
 *   k6 run --vus 200 --duration 60s load-test.js
 * 
 *   # 500+ concurrent users (stress test)
 *   k6 run --vus 500 --duration 120s load-test.js
 * 
 *   # Use scenarios for ramping
 *   k6 run load-test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('error_rate');
const cacheHitRate = new Rate('cache_hit_rate');
const requestDuration = new Trend('request_duration_ms');
const totalRequests = new Counter('total_requests');

// Test configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost';

// Thresholds for pass/fail criteria
export const options = {
  // Default scenario: ramping VUs
  scenarios: {
    // Scenario 1: Baseline (50 concurrent users)
    baseline: {
      executor: 'constant-vus',
      vus: 50,
      duration: '60s',
      tags: { scenario: 'baseline' },
      startTime: '0s',
    },
    // Scenario 2: Moderate load (200 concurrent users)
    moderate: {
      executor: 'constant-vus',
      vus: 200,
      duration: '60s',
      tags: { scenario: 'moderate' },
      startTime: '65s',
    },
    // Scenario 3: High load (500+ concurrent users)
    stress: {
      executor: 'ramping-vus',
      startVUs: 100,
      stages: [
        { duration: '30s', target: 300 },
        { duration: '60s', target: 500 },
        { duration: '30s', target: 500 },
        { duration: '30s', target: 0 },
      ],
      tags: { scenario: 'stress' },
      startTime: '130s',
    },
  },
  
  // Performance thresholds
  thresholds: {
    // P95 latency should be under 500ms
    'http_req_duration{scenario:baseline}': ['p(95)<500'],
    'http_req_duration{scenario:moderate}': ['p(95)<1000'],
    'http_req_duration{scenario:stress}': ['p(95)<2000'],
    
    // Error rate should be under 1% for baseline, 5% for stress
    'error_rate{scenario:baseline}': ['rate<0.01'],
    'error_rate{scenario:moderate}': ['rate<0.02'],
    'error_rate{scenario:stress}': ['rate<0.05'],
    
    // Overall thresholds
    http_req_failed: ['rate<0.05'],          // <5% errors overall
    http_req_duration: ['p(95)<2000'],        // p95 < 2s overall
  },
};

// Request helper with metrics tracking
function makeRequest(url, name) {
  const response = http.get(url, {
    tags: { name: name },
    timeout: '30s',
  });
  
  totalRequests.add(1);
  requestDuration.add(response.timings.duration);
  
  const isSuccess = response.status === 200;
  const isCacheHit = response.headers['X-Cache'] === 'HIT';
  
  errorRate.add(!isSuccess);
  if (isSuccess) {
    cacheHitRate.add(isCacheHit);
  }
  
  return response;
}

// Main test function
export default function () {
  // Health check (fast, should always work)
  group('Health Check', function () {
    const res = makeRequest(`${BASE_URL}/health`, 'health');
    check(res, {
      'health status is 200': (r) => r.status === 200,
      'health response has status': (r) => {
        try {
          return JSON.parse(r.body).status !== undefined;
        } catch {
          return false;
        }
      },
    });
  });
  
  // API data endpoint (main workload)
  group('API Data', function () {
    // Test upstream source
    const apiRes = makeRequest(`${BASE_URL}/api/data?endpoint=/posts`, 'api_data');
    check(apiRes, {
      'api status is 200': (r) => r.status === 200,
      'api has X-Cache header': (r) => r.headers['X-Cache'] !== undefined,
      'api response is valid JSON': (r) => {
        try {
          JSON.parse(r.body);
          return true;
        } catch {
          return false;
        }
      },
    });
  });
  
  // CSV data endpoint
  group('CSV Data', function () {
    const csvRes = makeRequest(`${BASE_URL}/api/data?source=csv&dataset=users&limit=10`, 'csv_data');
    check(csvRes, {
      'csv status is 200': (r) => r.status === 200,
      'csv has success field': (r) => {
        try {
          return JSON.parse(r.body).success === true;
        } catch {
          return false;
        }
      },
    });
  });
  
  // Small sleep between iterations to simulate realistic user behavior
  sleep(0.1);
}

// Setup function - run once before the test
export function setup() {
  console.log(`Starting load test against ${BASE_URL}`);
  
  // Verify the target is reachable
  const healthRes = http.get(`${BASE_URL}/health`);
  if (healthRes.status !== 200) {
    throw new Error(`Target ${BASE_URL} is not reachable. Status: ${healthRes.status}`);
  }
  
  console.log('Target verified, starting load test...');
  return { startTime: new Date().toISOString() };
}

// Teardown function - run once after the test
export function teardown(data) {
  console.log(`Load test completed. Started at: ${data.startTime}`);
}
