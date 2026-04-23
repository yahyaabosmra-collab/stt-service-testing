import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '20s',
};

const audioData = open('./تكنولوجيا.m4a', 'b');

export default function () {
  const url = 'http://127.0.0.1:8005/stt/upload/';

  const payload = {
    audio: http.file(audioData, 'تكنولوجيا.m4a', 'audio/mp4'),
  };

  const res = http.post(url, payload);

  const ok = check(res, {
    'status is 202': (r) => r.status === 202,
  });

  if (!ok) {
    console.log(`STATUS: ${res.status}`);
    console.log(`BODY: ${res.body}`);
  }

  sleep(1);
}