import { http, HttpResponse } from 'msw'
import type { Project, Agent } from './data'
import {
  agents as initialAgents,
  assets,
  chapters,
  files,
  projects as initialProjects,
  promptTemplates,
  shotDetails,
  shots,
  timelineClips,
} from './data'

// 可变的项目列表，支持创建/编辑/删除（会话内生效）
let projectsList: Project[] = [...initialProjects]
let agentsList: Agent[] = [...initialAgents]

function nextProjectId(): string {
  const max = projectsList.reduce((m, p) => {
    const n = parseInt(p.id.replace(/\D/g, ''), 10)
    return isNaN(n) ? m : Math.max(m, n)
  }, 0)
  return `p${max + 1}`
}

export const handlers = [
  // 项目列表
  http.get('/api/projects', () => {
    return HttpResponse.json(projectsList, { status: 200 })
  }),

  // 单个项目详情
  http.get('/api/projects/:projectId', ({ params }) => {
    const { projectId } = params as { projectId: string }
    const project = projectsList.find((p) => p.id === projectId)
    if (!project) {
      return HttpResponse.json({ message: '项目不存在' }, { status: 404 })
    }
    return HttpResponse.json(project, { status: 200 })
  }),

  // 创建项目
  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as Partial<Project> & { name: string; description?: string; style?: string; seed?: number; unifyStyle?: boolean }
    const id = nextProjectId()
    const now = new Date().toISOString().slice(0, 16).replace('T', ' ')
    const newProject: Project = {
      id,
      name: body.name ?? '未命名项目',
      description: body.description ?? '',
      style: (body.style as Project['style']) ?? '现实主义',
      seed: typeof body.seed === 'number' ? body.seed : Math.floor(Math.random() * 99999),
      unifyStyle: body.unifyStyle ?? true,
      progress: 0,
      stats: { chapters: 0, roles: 0, scenes: 0, props: 0 },
      updatedAt: now,
    }
    projectsList = [...projectsList, newProject]
    return HttpResponse.json(newProject, { status: 201 })
  }),

  // 更新项目
  http.put('/api/projects/:projectId', async ({ params, request }) => {
    const { projectId } = params as { projectId: string }
    const idx = projectsList.findIndex((p) => p.id === projectId)
    if (idx === -1) return HttpResponse.json({ message: '项目不存在' }, { status: 404 })
    const body = (await request.json()) as Partial<Project>
    const now = new Date().toISOString().slice(0, 16).replace('T', ' ')
    projectsList = projectsList.map((p, i) =>
      i === idx
        ? { ...p, ...body, id: p.id, updatedAt: now }
        : p
    )
    return HttpResponse.json(projectsList[idx], { status: 200 })
  }),

  // 删除项目
  http.delete('/api/projects/:projectId', ({ params }) => {
    const { projectId } = params as { projectId: string }
    const idx = projectsList.findIndex((p) => p.id === projectId)
    if (idx === -1) return HttpResponse.json({ message: '项目不存在' }, { status: 404 })
    projectsList = projectsList.filter((p) => p.id !== projectId)
    return new HttpResponse(null, { status: 204 })
  }),

  // 项目下章节列表
  http.get('/api/projects/:projectId/chapters', ({ params }) => {
    const { projectId } = params as { projectId: string }
    const list = chapters.filter((c) => c.projectId === projectId)
    return HttpResponse.json(list, { status: 200 })
  }),

  // 某章节的分镜列表
  http.get('/api/chapters/:chapterId/shots', ({ params }) => {
    const { chapterId } = params as { chapterId: string }
    const list = shots.filter((s) => s.chapterId === chapterId)
    return HttpResponse.json(list, { status: 200 })
  }),

  // 单个分镜详情（镜头属性）
  http.get('/api/shots/:shotId', ({ params }) => {
    const { shotId } = params as { shotId: string }
    const detail = shotDetails.find((s) => s.id === shotId)
    if (!detail) {
      return HttpResponse.json({ message: '分镜不存在' }, { status: 404 })
    }
    return HttpResponse.json(detail, { status: 200 })
  }),

  // 资产列表（可通过查询参数过滤）
  http.get('/api/assets', ({ request }) => {
    const url = new URL(request.url)
    const type = url.searchParams.get('type')
    const list = type ? assets.filter((a) => a.type === type) : assets
    return HttpResponse.json(list, { status: 200 })
  }),

  // 提示词模板列表
  http.get('/api/prompts/templates', () => {
    return HttpResponse.json(promptTemplates, { status: 200 })
  }),

  // 文件列表
  http.get('/api/files', () => {
    return HttpResponse.json(files, { status: 200 })
  }),

  // 某项目的时间线数据
  http.get('/api/projects/:projectId/timeline', () => {
    return HttpResponse.json(timelineClips, { status: 200 })
  }),

  // Agent 列表
  http.get('/api/agents', () => {
    return HttpResponse.json(agentsList, { status: 200 })
  }),

  // 单个 Agent 详情
  http.get('/api/agents/:id', ({ params }) => {
    const { id } = params as { id: string }
    const agent = agentsList.find((a) => a.id === id)
    if (!agent) return HttpResponse.json({ message: 'Agent 不存在' }, { status: 404 })
    return HttpResponse.json(agent, { status: 200 })
  }),

  // 创建 Agent
  http.post('/api/agents', async ({ request }) => {
    const body = (await request.json()) as Partial<Agent> & { name: string; type: Agent['type']; description?: string }
    const id = `agent${Date.now()}`
    const now = new Date().toISOString().slice(0, 10)
    const newAgent: Agent = {
      id,
      name: body.name ?? '未命名 Agent',
      type: body.type ?? 'other',
      description: body.description ?? '',
      isDefault: false,
      version: 'v1.0',
      updatedAt: now,
      createdAt: now,
      createdBy: 'extreme',
      updatedBy: 'extreme',
    }
    agentsList = [...agentsList, newAgent]
    return HttpResponse.json(newAgent, { status: 201 })
  }),

  // 更新 Agent（含设置默认）
  http.put('/api/agents/:id', async ({ params, request }) => {
    const { id } = params as { id: string }
    const idx = agentsList.findIndex((a) => a.id === id)
    if (idx === -1) return HttpResponse.json({ message: 'Agent 不存在' }, { status: 404 })
    const body = (await request.json()) as Partial<Agent>
    const now = new Date().toISOString().slice(0, 10)
    const updated = { ...agentsList[idx], ...body, id: agentsList[idx].id, updatedAt: now }
    if (body.isDefault === true) {
      agentsList = agentsList.map((a) =>
        a.type === updated.type && a.id !== id ? { ...a, isDefault: false } : a
      )
      agentsList[idx] = updated
    } else {
      agentsList = agentsList.map((a, i) => (i === idx ? updated : a))
    }
    return HttpResponse.json(agentsList[idx], { status: 200 })
  }),

  // 删除 Agent
  http.delete('/api/agents/:id', ({ params }) => {
    const { id } = params as { id: string }
    const idx = agentsList.findIndex((a) => a.id === id)
    if (idx === -1) return HttpResponse.json({ message: 'Agent 不存在' }, { status: 404 })
    agentsList = agentsList.filter((a) => a.id !== id)
    return new HttpResponse(null, { status: 204 })
  }),
]


