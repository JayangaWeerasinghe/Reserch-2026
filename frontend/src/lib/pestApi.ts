import api from './api'

const PEST_API_URL =
  import.meta.env.VITE_PEST_API_URL || 'http://localhost:8003'

export interface PestQuality {
  passed: boolean
  warnings: string[]
  blur_score: number
  brightness: number
  contrast: number
  edge_density: number
  resolution: string
}

export interface PestDetectionResult {
  prediction: string
  confidence: number
  status: 'known' | 'maybe' | 'unknown'
  source:
    | 'base_model'
    | 'few_shot'
    | 'fine_tuned'
    | 'quality_check'
    | 'ood'
  quality: PestQuality
  gradcam_image_base64: string | null
  message: string
  few_shot_similarity: number | null
  ood_score: number | null
  ood_method: string
}

export interface FewShotRegisterResult {
  class_name: string
  images_used: number
  epochs?: number
  fine_tuned_layers?: string[]
  message: string
}

export interface FewShotClassesResult {
  classes: string[]
}


/* =========================================================
   PEST DETECTION
   Docker research backend
   POST http://localhost:8003/detect
   ========================================================= */

export async function detectPest(
  image: File
): Promise<PestDetectionResult> {
  const form = new FormData()

  // Docker research backend /detect expects "file"
  form.append('file', image, image.name)

  const { data } = await api.post<PestDetectionResult>(
    `${PEST_API_URL}/detect`,
    form,
    {
      timeout: 240000,
    }
  )

  return data
}
/* =========================================================
   GET LEARNED PEST CLASSES
   GET /api/v1/few-shot/classes
   ========================================================= */

export async function getLearnedPestClasses(): Promise<string[]> {

  const { data } =
    await api.get<FewShotClassesResult>(
      `${PEST_API_URL}/api/v1/few-shot/classes`
    )

  return Array.isArray(data.classes)
    ? data.classes
    : []
}


/* =========================================================
   TEACH NEW PEST
   POST /api/v1/few-shot/fine-tune
   or
   POST /api/v1/few-shot/register
   ========================================================= */

export async function teachNewPest(
  className: string,
  files: File[],
  method: 'fine_tune' | 'prototype',
): Promise<FewShotRegisterResult> {

  if (!className.trim()) {
    throw new Error('Please enter a new pest name.')
  }

  if (files.length < 5 || files.length > 20) {
    throw new Error(
      'Please select between 5 and 20 labelled images.'
    )
  }

  const form = new FormData()

  /*
   * Swagger confirms:
   *
   * class_name → required string
   * files      → required array of files
   */

  form.append(
    'class_name',
    className.trim()
  )

  files.forEach((file) => {
    form.append(
      'files',
      file,
      file.name
    )
  })


  const endpoint =
    method === 'fine_tune'
      ? `${PEST_API_URL}/api/v1/few-shot/fine-tune`
      : `${PEST_API_URL}/api/v1/few-shot/register`


  const { data } =
    await api.post<FewShotRegisterResult>(
      endpoint,
      form,
      {
        timeout: 600000,
      }
    )

  return data
}


/* =========================================================
   DELETE LEARNED PEST
   DELETE /api/v1/few-shot/classes/{class_name}
   ========================================================= */

export async function deleteLearnedPest(
  className: string
): Promise<void> {

  await api.delete(
    `${PEST_API_URL}/api/v1/few-shot/classes/${encodeURIComponent(
      className
    )}`
  )
}