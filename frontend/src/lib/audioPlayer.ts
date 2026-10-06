// App-wide singleton so only one synthesised speech clip ever plays at a time.
// Any component that starts playback must call registerAudio() first — it
// stops whatever other clip is currently active before handing back control.
let current: HTMLAudioElement | null = null

export function registerAudio(audio: HTMLAudioElement) {
  if (current && current !== audio) {
    current.pause()
    current.currentTime = 0
  }
  current = audio
}

export function stopAllAudio() {
  if (current) {
    current.pause()
    current.currentTime = 0
  }
  current = null
}
