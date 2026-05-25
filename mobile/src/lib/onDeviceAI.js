function getOnDeviceAIConfig() {
  return {
    feature: "on-device-whisper",
    platforms: {
      ios: {
        enabled: true,
        model: "whisper-tiny",
        notes: "Use Core ML runtime for whisper-tiny on-device."
      },
      android: {
        enabled: true,
        model: "whisper-tiny",
        notes: "Use NNAPI runtime for whisper-tiny on-device."
      }
    }
  };
}

module.exports = {
  getOnDeviceAIConfig
};
