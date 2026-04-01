import { Card, Button, Tag, Statistic, Row, Col, Progress, Space, Spin } from 'antd'
import { RiseOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { chapterStatusMap } from '../constants'
import type { TabKey } from '../constants'
import { getProjectChaptersPath, getProjectEditorPath } from '../routes'
import { useProject, useChapters } from '../hooks/useProjectData'
import { ensureHasShotsBeforeShooting } from '../ensureHasShotsBeforeShooting'

export function DashboardTab({ onSelectTab }: { onSelectTab: (tab: TabKey) => void }) {
  const navigate = useNavigate()
  const { projectId } = useParams<{ projectId: string }>()
  const { project, loading: projectLoading } = useProject(projectId)
  const { chapters, loading: chaptersLoading } = useChapters(projectId)

  const loading = projectLoading || chaptersLoading
  const incompleteChapters = chapters.filter((c) => c.status !== 'done')
  const latestChapter = chapters.find((c) => c.status === 'shooting') ?? incompleteChapters[0]

  if (loading && !project) {
    return (
      <div className="flex justify-center items-center py-16">
        <Spin size="large" tip="加载中…" />
      </div>
    )
  }
  if (!project) {
    return null
  }

  const totalShots = chapters.reduce((s, c) => s + c.storyboardCount, 0)
  const completedShots = Math.round((totalShots * project.progress) / 100)
  const incompleteCount = incompleteChapters.length

  return (
    <div className="space-y-6">
      <Card size="small">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="font-medium">快速开始</div>
            <div className="text-xs text-gray-500">
              {latestChapter
                ? `继续拍摄：第${latestChapter.index}章（${latestChapter.title}）`
                : '暂无进行中的章节，可先创建章节或进入章节管理'}
            </div>
          </div>
          <Space wrap>
            <Button onClick={() => onSelectTab('chapters')}>创建/管理章节</Button>
            <Button onClick={() => projectId && navigate(getProjectEditorPath(projectId))}>进入后期剪辑</Button>
            <Button
              type="primary"
              icon={<VideoCameraOutlined />}
              disabled={!latestChapter}
              onClick={() =>
                ensureHasShotsBeforeShooting({
                  projectId,
                  chapterId: latestChapter?.id,
                  storyboardCount: latestChapter?.storyboardCount,
                  navigate,
                })
              }
            >
              继续拍摄
            </Button>
          </Space>
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="h-full">
            <Statistic title="未完成章节" value={incompleteCount} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="h-full">
            <Statistic title="已生成片段/总分镜" value={completedShots} suffix={`/ ${totalShots}`} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="h-full">
            <Statistic title="资产覆盖率" value={76} suffix="%" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="h-full">
            <Statistic title="整体进度" value={project.progress} suffix="%" prefix={<RiseOutlined />} />
            <Progress
              percent={project.progress}
              showInfo={false}
              size="small"
              strokeColor={{ from: '#6366f1', to: '#a855f7' }}
              className="mt-1"
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="章节进度"
        size="small"
        extra={
          <Button type="link" onClick={() => projectId && navigate(getProjectChaptersPath(projectId))}>
            查看全部
          </Button>
        }
      >
        <div className="flex gap-3 overflow-x-auto pb-2" style={{ minHeight: 140 }}>
          {chapters.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 py-8">
              还没有任何章节，
              <Button type="link" className="p-0" onClick={() => onSelectTab('chapters')}>
                立即创建第一章
              </Button>
            </div>
          ) : (
            chapters.slice(0, 8).map((ch) => (
              <Card
                key={ch.id}
                size="small"
                hoverable
                className="shrink-0 cursor-pointer"
                style={{ width: 280 }}
                onClick={() =>
                  ensureHasShotsBeforeShooting({
                    projectId,
                    chapterId: ch.id,
                    storyboardCount: ch.storyboardCount,
                    navigate,
                  })
                }
              >
                <div className="font-medium truncate">
                  第{ch.index}集 {ch.title}
                </div>
                <Tag color={chapterStatusMap[ch.status].color} className="mt-1">
                  {chapterStatusMap[ch.status].text}
                </Tag>
                <div className="text-xs text-gray-500 mt-1">
                  分镜 {ch.storyboardCount} · {ch.updatedAt}
                </div>
              </Card>
            ))
          )}
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={14}>
          <Card title="最近活动" size="small">
            <ul className="list-none pl-0 m-0 space-y-2 text-sm text-gray-600">
              <li>· 生成第5章第12镜参考图</li>
              <li>· 更新第3章分镜脚本</li>
              <li>· 完成第2章拍摄</li>
            </ul>
            <Button type="link" className="p-0 mt-2">
              查看更多
            </Button>
          </Card>
        </Col>
        <Col xs={24} md={10}>
          <Card title="资产健康快照" size="small">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>角色</span>
                <span className="text-gray-500">{project.stats.roles} 项</span>
              </div>
              <Progress percent={80} size="small" showInfo={false} />
              <div className="flex justify-between text-sm">
                <span>场景</span>
                <span className="text-gray-500">{project.stats.scenes} 项</span>
              </div>
              <Progress percent={60} size="small" showInfo={false} />
              <div className="flex justify-between text-sm">
                <span>道具</span>
                <span className="text-gray-500">{project.stats.props} 项</span>
              </div>
              <Progress percent={75} size="small" showInfo={false} />
            </div>
            <Button type="link" className="p-0 mt-2" onClick={() => navigate('/assets')}>
              管理资产
            </Button>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

