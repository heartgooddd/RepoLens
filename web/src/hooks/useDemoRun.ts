import { useEffect, useState } from 'react'
import { stages } from '../demo/pocketflow'
import type { RunParameters, RunState } from '../types'

export function useDemoRun() {
  const [run, setRun] = useState<RunState>({ status: 'idle' })

  useEffect(() => {
    if (run.status !== 'running') return
    const timer = window.setTimeout(() => {
      if (run.parameters.scenario === 'failure' && run.step === 2) {
        setRun({ ...run, status: 'error' })
      } else if (run.step === stages.length - 1) {
        setRun({ status: 'success', parameters: run.parameters })
      } else {
        setRun({ ...run, step: run.step + 1 })
      }
    }, 800)
    return () => window.clearTimeout(timer)
  }, [run])

  return {
    run,
    start: (parameters: RunParameters) => setRun({ status: 'running', step: 0, parameters: { ...parameters } }),
    stop: () => setRun(current => current.status === 'running' ? { ...current, status: 'stopped' } : current),
    reset: () => setRun({ status: 'idle' }),
  }
}
