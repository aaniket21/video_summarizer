const assert = require("assert");

const { getOnDeviceAIConfig } = require("../src/lib/onDeviceAI");

const config = getOnDeviceAIConfig();

assert.strictEqual(config.feature, "on-device-whisper");
assert.strictEqual(config.platforms.ios.enabled, true);
assert.strictEqual(config.platforms.android.enabled, true);
assert.strictEqual(config.platforms.ios.model, "whisper-tiny");
assert.strictEqual(config.platforms.android.model, "whisper-tiny");

console.log("on-device ai config ok");
