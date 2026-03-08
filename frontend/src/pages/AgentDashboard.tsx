import React, { useState, useEffect } from 'react';
import { Alert, Card, Col, Row, Statistic, Table, Tag } from 'antd';

const AgentDashboard: React.FC = () => {
  const [agentStatus, setAgentStatus] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgentStatus();
    fetchMetrics();
    const interval = setInterval(() => {
      fetchAgentStatus();
      fetchMetrics();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchAgentStatus = async () => {
    try {
      const response = await fetch('/api/agents/status');
      const data = await response.json();
      setAgentStatus(data.data || []);
    } catch (error) {
      console.error('获取Agent状态失败:', error);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await fetch('/api/monitoring/metrics');
      const data = await response.json();
      setMetrics(data.data || {});
    } catch (error) {
      console.error('获取指标失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'green';
      case 'busy': return 'orange';
      case 'error': return 'red';
      default: return 'default';
    }
  };

  const columns = [
    { title: 'Agent名称', dataIndex: 'name', key: 'name' },
    { title: '角色', dataIndex: 'role', key: 'role' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{status}</Tag>
    },
    { title: '最后心跳', dataIndex: 'last_heartbeat', key: 'last_heartbeat' },
    { title: '任务数', dataIndex: 'task_count', key: 'task_count' },
  ];

  return (
    <div>
      <Alert
        message="Agent系统运行中"
        description={`${agentStatus.filter(a => a.status === 'online').length} 个Agent在线`}
        type="success"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic title="今日爬取专利" value={metrics.today_crawled || 0} prefix="#" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="召回率" value={metrics.recall_rate || 0} suffix="%" precision={2} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="准确率" value={metrics.accuracy_rate || 0} suffix="%" precision={2} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="向量库文档" value={metrics.doc_count || 0} prefix="#" />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card title="Agent状态">
            <Table
              columns={columns}
              dataSource={agentStatus}
              loading={loading}
              rowKey="name"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default AgentDashboard;
