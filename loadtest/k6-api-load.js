import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('error_rate');

const targetUrl = __ENV.TARGET_URL || 'http://host.docker.internal/api/data?source=csv&endpoint=/users&limit=20';
const thinkTime = Number(__ENV.THINK_TIME_MS || 50) / 1000;

export const options = {
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<3000'],
    error_rate: ['rate<0.05'],
  },
};

export default function () {
  const res = http.get(targetUrl, {
    headers: {
      Accept: 'application/json',
    },
    timeout: '10s',
  });

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has json body': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.success === true;
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!ok);
  sleep(thinkTime);
}
