/**
 * 爬虫任务调度管理页面
 * Patent Crawler Task Scheduler Management Page
 *
 * 功能：
 * - 查看所有定时任务配置
 * - 手动触发爬取任务
 * - 监控任务执行状态
 * - 查看任务历史记录
 * - 管理数据源配置
 */
import { useState, useEffect } from 'react';
import {
  Card, Button, Select, InputNumber, message, Table, Tag, Progress,
  Tabs, Space, Row, Col, Statistic, Alert, Badge, Modal, Form, Input,
  Descriptions, Timeline, Switch, Divider, Tooltip, Empty, Spin,
  Drawer, List, Typography, Popconfirm, Collapse, Radio
} from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, 
  ScheduleOutlined, ClockCircleOutlined, CheckCircleOutlined,
  CloseCircleOutlined, SyncOutlined, SettingOutlined, HistoryOutlined,
  DatabaseOutlined, FileTextOutlined, DeleteOutlined, EyeOutlined,
  ApiOutlined, WarningOutlined, ThunderboltOutlined, InfoCircleOutlined,
  ClearOutlined, RobotOutlined, LineChartOutlined
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import dayjs from 'dayjs';
import type { RootState } from '../store';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;
const { TextArea } = Input;
const { Panel } = Collapse;

// ==================== 类型定义 ====================
interface TaskSchedule {
  task_name: string;
  description: string;
  schedule: string;
  queue: string;
  enabled: boolean;
  last_run?: string;
  next_run?: string;
  run_count?: number;
}

interface TaskExecution {
  task_id: string;
  task_name: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';
  progress: number;
  source?: string;
  started_at?: string;
  completed_at?: string;
  duration?: number;
  result?: any;
  error?: string;
  metadata?: {
    patents_crawled?: number;
    patents_indexed?: number;
    data_source?: string;
  };
}

interface CrawlStats {
  total_patents: number;
  active_tasks: number;
  success_rate: number;
  avg_duration: number;
  total_crawls_today: number;
  last_crawl_time: string;
}

// ==================== 定时任务配置数据 ====================
const SCHEDULED_TASKS: TaskSchedule[] = [
  {
    task_name: 'patent-full-crawl-monthly',
    description: '全量爬取各国专利数据',
    schedule: '每月1日 2:00',
    queue: 'crawl',
    enabled: true,
    run_count: 3,
    last_run: '2026-02-01 02:00:00',
    next_run: '2026-03-01 02:00:00'
  },
  {
    task_name: 'patent-incremental-crawl-6h',
    description: '增量爬取最近6小时专利',
    schedule: '每6小时 (00:00, 06:00, 12:00, 18:00)',
    queue: 'crawl',
    enabled: true,
    run_count: 156,
    last_run: '2026-02-22 12:00:00',
    next_run: '2026-02-22 18:00:00'
  },
  {
    task_name: 'patent-incremental-crawl-1h',
    description: '快速增量爬取（每小时）',
    schedule: '每小时整点',
    queue: 'crawl',
    enabled: true,
    run_count: 538,
    last_run: '2026-02-22 17:00:00',
    next_run: '2026-02-22 18:00:00'
  },
  {
    task_name: 'rag-performance-evaluation-daily',
    description: 'RAG性能评估',
    schedule: '每天 3:00',
    queue: 'rag',
    enabled: true,
    run_count: 22,
    last_run: '2026-02-22 03:00:00',
    next_run: '2026-02-23 03:00:00'
  },
  {
    task_name: 'rag-accuracy-test-6h',
    description: 'RAG准确率测试',
    schedule: '每6小时30分',
    queue: 'rag',
    enabled: true,
    run_count: 89,
    last_run: '2026-02-22 12:30:00',
    next_run: '2026-02-22 18:30:00'
  },
  {
    task_name: 'vector-db-optimize-weekly',
    description: '向量库优化',
    schedule: '每周日 4:00',
    queue: 'rag',
    enabled: true,
    run_count: 8,
    last_run: '2026-02-16 04:00:00',
    next_run: '2026-02-23 04:00:00'
  },
  {
    task_name: 'cleanup-logs-weekly',
    description: '清理旧日志文件',
    schedule: '每周一 4:00',
    queue: 'cleanup',
    enabled: true,
    run_count: 8,
    last_run: '2026-02-17 04:00:00',
    next_run: '2026-02-24 04:00:00'
  },
  {
    task_name: 'cleanup-temp-files-daily',
    description: '清理临时文件',
    schedule: '每天 5:00',
    queue: 'cleanup',
    enabled: true,
    run_count: 52,
    last_run: '2026-02-22 05:00:00',
    next_run: '2026-02-23 05:00:00'
  },
  {
    task_name: 'cleanup-failed-tasks-weekly',
    description: '清理失败任务记录',
    schedule: '每周二 2:00',
    queue: 'cleanup',
    enabled: true,
    run_count: 8,
    last_run: '2026-02-18 02:00:00',
    next_run: '2026-02-25 02:00:00'
  },
  {
    task_name: 'cleanup-cache-daily',
    description: '清理缓存数据',
    schedule: '每天 6:00',
    queue: 'cleanup',
    enabled: true,
    run_count: 52,
    last_run: '2026-02-22 06:00:00',
    next_run: '2026-02-23 06:00:00'
  }
];

// ==================== 主组件 ====================
export function CrawlManagement() {
  const [activeTab, setActiveTab] = useState('overview');
  
  // 统计数据
  const [stats, setStats] = useState<CrawlStats>({
    total_patents: 125430,
    active_tasks: 3,
    success_rate: 96.5,
    avg_duration: 245.3,
    total_crawls_today: 24,
    last_crawl_time: '2026-02-22 17:00:00'
  });
  
  // 定时任务
  const [scheduledTasks, setScheduledTasks] = useState<TaskSchedule[]>(SCHEDULED_TASKS);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  
  // 任务执行记录
  const [taskExecutions, setTaskExecutions] = useState<TaskExecution[]>([
    {
      task_id: '550e8400-e29b-41d4-a716-446655440001',
      task_name: 'patent-incremental-crawl-6h',
      status: 'SUCCESS',
      progress: 100,
      source: 'USPTO',
      started_at: '2026-02-22 12:00:00',
      completed_at: '2026-02-22 15:23:45',
      duration: 203.75,
      metadata: {
        patents_crawled: 1247,
        patents_indexed: 1234,
        data_source: 'USPTO'
      }
    },
    {
      task_id: '550e8400-e29b-41d4-a716-446655440002',
      task_name: 'patent-incremental-crawl-1h',
      status: 'STARTED',
      progress: 67,
      source: 'CNIPA',
      started_at: '2026-02-22 17:00:00',
      metadata: {
        patents_crawled: 234,
        data_source: 'CNIPA'
      }
    },
    {
      task_id: '550e8400-e29b-41d4-a716-446655440003',
      task_name: 'rag-performance-evaluation-daily',
      status: 'SUCCESS',
      progress: 100,
      started_at: '2026-02-22 03:00:00',
      completed_at: '2026-02-22 03:12:34',
      duration: 734,
      result: {
        recall_rate: 96.8,
        accuracy_rate: 97.2,
        mrr: 0.892
      }
    }
  ]);
  
  // 手动触发配置
  const [manualConfig, setManualConfig] = useState({
    source: 'cnipa',
    query: '*',
    limit: 1000,
    hours: 24
  });
  
  // 任务详情Modal
  const [taskDetailModal, setTaskDetailModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskExecution | null>(null);
  
  // 日志查看Modal
  const [logModal, setLogModal] = useState(false);
  const [taskLogs, setTaskLogs] = useState('');
  
  // 加载状态
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  // ==================== API调用 ====================
  
  const fetchScheduledTasks = async () => {
    try {
      setScheduleLoading(true);
      // 实际调用API
      // const result = await api.getScheduledTasks();
      // setScheduledTasks(result.data);
    } catch (error) {
      message.error('获取定时任务列表失败');
    } finally {
      setScheduleLoading(false);
    }
  };

  const fetchTaskExecutions = async () => {
    try {
      setLoading(true);
      // 实际调用API
      // const result = await api.getTaskExecutions();
      // setTaskExecutions(result.data);
    } catch (error) {
      message.error('获取任务执行记录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleFullCrawl = async () => {
    try {
      setTriggering(true);
      const response = await fetch('/api/crawl/full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sources: ['cnipa', 'uspto', 'epo', 'wipo'],
          query: manualConfig.query,
          limit: manualConfig.limit * 10
        })
      });
      const result = await response.json();
      if (result.code === 0) {
        message.success(`全量爬取任务已启动: ${result.data.task_id}`);
        fetchTaskExecutions();
      }
    } catch (error) {
      message.error('启动失败');
    } finally {
      setTriggering(false);
    }
  };

  const handleIncrementalCrawl = async () => {
    try {
      setTriggering(true);
      const response = await fetch('/api/crawl/incremental', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sources: [manualConfig.source],
          hours: manualConfig.hours
        })
      });
      const result = await response.json();
      if (result.code === 0) {
        message.success(`增量爬取任务已启动: ${result.data.task_id}`);
        fetchTaskExecutions();
      }
    } catch (error) {
      message.error('启动失败');
    } finally {
      setTriggering(false);
    }
  };

  const handleViewTaskDetail = (task: TaskExecution) => {
    setSelectedTask(task);
    setTaskDetailModal(true);
  };

  const handleViewLogs = async (taskId: string) => {
    try {
      // 实际调用API
      // const result = await api.getTaskLogs(taskId);
      // setTaskLogs(result.data.logs);
      setTaskLogs(`[2026-02-22 17:00:00] Task started: ${taskId}
[2026-02-22 17:00:05] Connecting to data source...
[2026-02-22 17:00:10] Fetching patent data...
[2026-02-22 17:00:45] Retrieved 234 patents so far...
[2026-02-22 17:01:30] Processing citations...
[2026-02-22 17:02:15] Indexing to vector database...
[2026-02-22 17:02:45] Retrieved 312 patents so far...
[2026-02-22 17:03:20] Task is still running...`);
      setLogModal(true);
    } catch (error) {
      message.error('获取任务日志失败');
    }
  };

  const handleToggleTask = async (taskName: string, enabled: boolean) => {
    try {
      // 实际调用API
      // await api.toggleTaskSchedule(taskName, enabled);
      setScheduledTasks(prev => 
        prev.map(task => 
          task.task_name === taskName ? { ...task, enabled } : task
        )
      );
      message.success(`${enabled ? '启用' : '禁用'}任务成功`);
    } catch (error) {
      message.error('操作失败');
    }
  };

  // ==================== 表格列定义 ====================
  
  const executionColumns: ColumnsType<TaskExecution> = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 200,
      ellipsis: true,
      render: (id: string) => (
        <Tooltip title={id}>
          <Text copyable={{ text: id }} ellipsis style={{ maxWidth: 180 }}>
            {id}
          </Text>
        </Tooltip>
      )
    },
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      render: (name: string) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {SCHEDULED_TASKS.find(t => t.task_name === name)?.description}
          </Text>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string, record: TaskExecution) => {
        const statusConfig: Record<string, { color: string; text: string; icon: React.ReactNode }> = {
          PENDING: { color: 'default', text: '等待中', icon: <ClockCircleOutlined /> },
          STARTED: { color: 'processing', text: '运行中', icon: <SyncOutlined spin /> },
          SUCCESS: { color: 'success', text: '成功', icon: <CheckCircleOutlined /> },
          FAILURE: { color: 'error', text: '失败', icon: <CloseCircleOutlined /> },
          RETRY: { color: 'warning', text: '重试中', icon: <ReloadOutlined spin /> },
          REVOKED: { color: 'default', text: '已撤销', icon: <CloseCircleOutlined /> }
        };
        const config = statusConfig[status] || statusConfig['PENDING'];
        return (
          <Badge 
            status={config.color as any} 
            text={<span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>{config.icon} {config.text}</span>}
          />
        );
      }
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 150,
      render: (progress: number) => (
        <Progress 
          percent={progress} 
          size="small"
          status={progress >= 100 ? 'success' : 'active'}
        />
      )
    },
    {
      title: '数据源',
      dataIndex: 'metadata',
      key: 'source',
      width: 100,
      render: (meta?: any) => meta?.data_source || meta?.source || '-'
    },
    {
      title: '爬取专利数',
      dataIndex: 'metadata',
      key: 'patents',
      width: 100,
      render: (meta?: any) => meta?.patents_crawled ?? '-'
    },
    {
      title: '持续时间',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (duration?: number) => {
        if (!duration) return '-';
        if (duration < 60) return `${duration.toFixed(1)}秒`;
        return `${(duration / 60).toFixed(1)}分钟`;
      }
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 160,
      render: (time?: string) => time ? dayjs(time).format('MM-DD HH:mm:ss') : '-'
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right' as const,
      render: (_: any, record: TaskExecution) => (
        <Space>
          <Tooltip title="查看详情">
            <Button 
              type="link" 
              size="small" 
              icon={<EyeOutlined />}
              onClick={() => handleViewTaskDetail(record)}
            />
          </Tooltip>
          <Tooltip title="查看日志">
            <Button 
              type="link" 
              size="small" 
              icon={<FileTextOutlined />}
              onClick={() => handleViewLogs(record.task_id)}
            />
          </Tooltip>
        </Space>
      )
    }
  ];

  const scheduleColumns: ColumnsType<TaskSchedule> = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      render: (name: string) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description'
    },
    {
      title: '调度规则',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 200,
      render: (schedule: string) => (
        <Space>
          <ScheduleOutlined style={{ color: '#1890ff' }} />
          <Text strong>{schedule}</Text>
        </Space>
      )
    },
    {
      title: '队列',
      dataIndex: 'queue',
      key: 'queue',
      width: 80,
      render: (queue: string) => {
        const colors: Record<string, string> = {
          crawl: 'green',
          rag: 'blue',
          cleanup: 'orange'
        };
        return <Tag color={colors[queue]}>{queue.toUpperCase()}</Tag>;
      }
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean) => (
        <Badge 
          status={enabled ? 'success' : 'default'} 
          text={enabled ? '已启用' : '已禁用'}
        />
      )
    },
    {
      title: '执行次数',
      dataIndex: 'run_count',
      key: 'run_count',
      width: 100,
      render: (count?: number) => count || '-'
    },
    {
      title: '下次运行',
      dataIndex: 'next_run',
      key: 'next_run',
      width: 160,
      render: (time?: string) => time ? dayjs(time).format('YYYY-MM-DD HH:mm:ss') : '-'
    },
    {
      title: '启用/禁用',
      key: 'toggle',
      width: 100,
      render: (_: any, record: TaskSchedule) => (
        <Switch
          checked={record.enabled}
          onChange={(checked) => handleToggleTask(record.task_name, checked)}
        />
      )
    }
  ];

  // ==================== 渲染函数 ====================
  
  return (
    <div style={{ padding: '24px' }}>
      <Row gutter={[24, 24]}>
        <Col span={24}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 页面标题 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <RobotOutlined style={{ fontSize: 32, color: '#1890ff' }} />
                <Title level={2} style={{ margin: 0 }}>
                  专利爬虫任务调度中心
                </Title>
              </Space>
              <Space>
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={() => {
                    fetchTaskExecutions();
                    fetchScheduledTasks();
                  }}
                  loading={loading}
                >
                  刷新
                </Button>
              </Space>
            </div>

            {/* 统计卡片 */}
            <Row gutter={16}>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="总专利数"
                    value={stats.total_patents}
                    prefix={<DatabaseOutlined />}
                    valueStyle={{ color: '#3f8600' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="运行中任务"
                    value={stats.active_tasks}
                    prefix={<SyncOutlined spin />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="今日爬取次数"
                    value={stats.total_crawls_today}
                    prefix={<ThunderboltOutlined />}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="成功率"
                    value={stats.success_rate}
                    suffix="%"
                    prefix={<CheckCircleOutlined />}
                    valueStyle={{ color: '#cf1322' }}
                  />
                </Card>
              </Col>
            </Row>

            {/* 功能提示 */}
            <Alert
              message="任务调度系统"
              description="Celery Beat 定时任务调度器，支持全量/增量爬取、RAG性能评估、VectorDB优化、日志清理等10个定时任务。可通过下方标签页查看和配置。"
              type="info"
              showIcon
              icon={<InfoCircleOutlined />}
            />

            {/* 标签页 */}
            <Card>
              <Tabs activeKey={activeTab} onChange={setActiveTab}>
                {/* 手动触发 */}
                <TabPane tab="手动触发" key="manual">
                  <Space direction="vertical" size="large" style={{ width: '100%' }}>
                    <Alert
                      message="手动触发爬取任务"
                      description="手动触发不会影响定时调度任务的正常执行。建议谨慎使用全量爬取，会消耗大量时间和资源。"
                      type="warning"
                      showIcon
                      icon={<WarningOutlined />}
                    />

                    <Card title="触发配置" size="small">
                      <Form layout="inline">
                        <Form.Item label="数据源">
                          <Select 
                            value={manualConfig.source} 
                            onChange={(v) => setManualConfig({...manualConfig, source: v})}
                            style={{ width: 150 }}
                          >
                            <Option value="cnipa">CNIPA</Option>
                            <Option value="uspto">USPTO</Option>
                            <Option value="epo">EPO</Option>
                            <Option value="wipo">WIPO</Option>
                          </Select>
                        </Form.Item>
                        <Form.Item label="查询条件">
                          <Input 
                            placeholder="* (全部)" 
                            value={manualConfig.query}
                            onChange={(e) => setManualConfig({...manualConfig, query: e.target.value})}
                            style={{ width: 200 }}
                          />
                        </Form.Item>
                        <Form.Item label="数量限制">
                          <InputNumber
                            value={manualConfig.limit}
                            onChange={(v) => setManualConfig({...manualConfig, limit: v || 1000})}
                            min={100}
                            max={10000}
                            step={100}
                            style={{ width: 120 }}
                          />
                        </Form.Item>
                        <Form.Item label="时间范围(小时)">
                          <InputNumber
                            value={manualConfig.hours}
                            onChange={(v) => setManualConfig({...manualConfig, hours: v || 24})}
                            min={1}
                            max={168}
                            style={{ width: 100 }}
                          />
                        </Form.Item>
                      </Form>

                      <Space style={{ marginTop: 16 }}>
                        <Button
                          type="primary"
                          size="large"
                          icon={<PlayCircleOutlined />}
                          onClick={handleFullCrawl}
                          loading={triggering}
                        >
                          触发全量爬取
                        </Button>
                        <Button
                          type="default"
                          size="large"
                          icon={<ReloadOutlined />}
                          onClick={handleIncrementalCrawl}
                          loading={triggering}
                        >
                          触发增量爬取
                        </Button>
                      </Space>
                    </Card>
                  </Space>
                </TabPane>

                {/* 任务执行记录 */}
                <TabPane 
                  tab={
                    <span>
                      <HistoryOutlined />
                      执行记录
                    </span>
                  }
                  key="executions"
                >
                  <Table
                    columns={executionColumns}
                    dataSource={taskExecutions}
                    rowKey="task_id"
                    loading={loading}
                    scroll={{ x: 1400 }}
                    pagination={{
                      pageSize: 10,
                      showSizeChanger: true,
                      showTotal: (total) => `共 ${total} 条记录`
                    }}
                  />
                </TabPane>

                {/* 定时任务配置 */}
                <TabPane
                  tab={
                    <span>
                      <ScheduleOutlined />
                      定时任务
                    </span>
                  }
                  key="schedule"
                >
                  <Table
                    columns={scheduleColumns}
                    dataSource={scheduledTasks}
                    rowKey="task_name"
                    loading={scheduleLoading}
                    pagination={false}
                  />
                </TabPane>
              </Tabs>
            </Card>
          </Space>
        </Col>
      </Row>

      {/* 任务详情Modal */}
      <Modal
        title={
          <Space>
            <InfoCircleOutlined style={{ color: '#1890ff' }} />
            任务执行详情
          </Space>
        }
        open={taskDetailModal}
        onCancel={() => setTaskDetailModal(false)}
        footer={[
          selectedTask?.status === 'STARTED' && (
            <Button key="cancel" danger type="primary">
              终止任务
            </Button>
          ),
          <Button key="close" type="primary" onClick={() => setTaskDetailModal(false)}>
            关闭
          </Button>
        ]}
        width={700}
      >
        {selectedTask && (
          <Descriptions bordered column={2}>
            <Descriptions.Item label="任务ID" span={2}>
              <Text copyable>{selectedTask.task_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="任务名称" span={2}>
              {selectedTask.task_name}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Badge 
                status={
                  selectedTask.status === 'SUCCESS' ? 'success' :
                  selectedTask.status === 'STARTED' ? 'processing' :
                  selectedTask.status === 'FAILURE' ? 'error' : 'default'
                } 
                text={selectedTask.status}
              />
            </Descriptions.Item>
            <Descriptions.Item label="进度">
              <Progress percent={selectedTask.progress} />
            </Descriptions.Item>
            {selectedTask.started_at && (
              <Descriptions.Item label="开始时间" span={2}>
                {dayjs(selectedTask.started_at).format('YYYY-MM-DD HH:mm:ss')}
              </Descriptions.Item>
            )}
            {selectedTask.completed_at && (
              <Descriptions.Item label="完成时间" span={2}>
                {dayjs(selectedTask.completed_at).format('YYYY-MM-DD HH:mm:ss')}
              </Descriptions.Item>
            )}
            {selectedTask.duration && (
              <Descriptions.Item label="持续时间" span={2}>
                {selectedTask.duration.toFixed(2)}秒 ({(selectedTask.duration / 60).toFixed(2)}分钟)
              </Descriptions.Item>
            )}
            {selectedTask.metadata && (
              <>
                {selectedTask.metadata.patents_crawled !== undefined && (
                  <Descriptions.Item label="爬取专利数">
                    {selectedTask.metadata.patents_crawled.toLocaleString()}
                  </Descriptions.Item>
                )}
                {selectedTask.metadata.patents_indexed !== undefined && (
                  <Descriptions.Item label="索引专利数">
                    {selectedTask.metadata.patents_indexed.toLocaleString()}
                  </Descriptions.Item>
                )}
                {selectedTask.metadata.data_source && (
                  <Descriptions.Item label="数据源">
                    {selectedTask.metadata.data_source}
                  </Descriptions.Item>
                )}
              </>
            )}
            {selectedTask.result && (
              <Descriptions.Item label="执行结果" span={2}>
                <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: 4 }}>
                  {JSON.stringify(selectedTask.result, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {selectedTask.error && (
              <Descriptions.Item label="错误信息" span={2}>
                <Alert message={selectedTask.error} type="error" />
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* 日志查看Modal */}
      <Modal
        title={
          <Space>
            <FileTextOutlined style={{ color: '#1890ff' }} />
            任务执行日志
          </Space>
        }
        open={logModal}
        onCancel={() => setLogModal(false)}
        footer={[
          <Button key="download" icon={<ApiOutlined />}>
            下载日志
          </Button>,
          <Button key="close" type="primary" onClick={() => setLogModal(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <div style={{ 
          background: '#1e1e1e', 
          color: '#d4d4d4', 
          padding: '16px', 
          borderRadius: '4px',
          maxHeight: '500px',
          overflow: 'auto',
          fontFamily: 'monospace',
          fontSize: '12px',
          lineHeight: 1.6
        }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{taskLogs}</pre>
        </div>
      </Modal>
    </div>
  );
}

export default CrawlManagement;
