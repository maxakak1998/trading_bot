---
trigger: always_on
description: Đây là các steps
---

Khi thay đổi code, upgrade hoặc thêm feature/indicators, luôn luôn phải có feature flag từ config.json.

Nếu 2 flag nào bị conflict với nhau, hãy throw error trong code khi 2 flag đó đều được enable.

