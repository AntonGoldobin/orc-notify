import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as soundsApi from '@/api/sounds'
import type { SoundIn, SoundOut, SoundPatch } from '@/api/types'

export const soundsKeys = {
  all: ['sounds'] as const,
  list: () => [...soundsKeys.all, 'list'] as const,
}

export function useSounds() {
  return useQuery({ queryKey: soundsKeys.list(), queryFn: soundsApi.listSounds })
}

export function useCreateSound() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: SoundIn) => soundsApi.createSound(input),
    onSuccess: (created) => {
      qc.setQueryData<SoundOut[]>(soundsKeys.list(), (prev) =>
        prev ? [created, ...prev] : [created],
      )
    },
  })
}

export function useUpdateSound() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: SoundPatch }) =>
      soundsApi.updateSound(id, patch),
    onSuccess: (updated) => {
      qc.setQueryData<SoundOut[]>(soundsKeys.list(), (prev) =>
        prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : [updated],
      )
    },
  })
}

export function useDeleteSound() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => soundsApi.deleteSound(id),
    onSuccess: (_void, id) => {
      qc.setQueryData<SoundOut[]>(soundsKeys.list(), (prev) =>
        prev ? prev.filter((s) => s.id !== id) : prev,
      )
    },
  })
}
