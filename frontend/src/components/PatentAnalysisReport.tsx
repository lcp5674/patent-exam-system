import React from 'react';
import { Card, Table, Tag, Descriptions, Typography, Alert, Space, Divider, List, Collapse } from 'antd';
import { RobotOutlined, FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';

const { Paragraph, Title, Text } = Typography;

// 专利分析报告组件
export const PatentAnalysisReport: React.FC<{
  data: any;
  rawContent?: string;
}> = ({ data, rawContent }) => {
  
  // 如果没有结构化数据，显示原始内容
  if (!data) {
    return rawContent ? (
      <Card>
        <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{rawContent}</Paragraph>
      </Card>
    ) : null;
  }

  // 检测数据结构类型并渲染相应组件
  const renderStructuredReport = () => {
    // 1. 标准专利分析报告结构
    if (data.请求书信息 || data.basicInfo || data.patentInfo) {
      return renderStandardPatentReport(data);
    }
    
    // 2. 新颖性分析结构
    if (data.noveltyAnalysis || data.新颖性分析) {
      return renderNoveltyAnalysis(data);
    }
    
    // 3. 创造性分析结构
    if (data.inventivenessAnalysis || data.创造性分析) {
      return renderInventivenessAnalysis(data);
    }
    
    // 4. 权利要求分析
    if (data.claims || data.权利要求) {
      return renderClaimsAnalysis(data);
    }
    
    // 5. 通用分析结构 - 尝试渲染任何JSON数据
    return renderGenericAnalysis(data);
  };

  // 渲染标准专利分析报告
  const renderStandardPatentReport = (reportData: any) => {
    const info = reportData.请求书信息 || reportData.basicInfo || reportData.patentInfo || {};
    const claims = reportData.权利要求书 || reportData.claims || {};
    const description = reportData.说明书 || reportData.description || {};
    const summary = reportData.摘要 || reportData.abstract || "";

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 专利基本信息 */}
        <Card title={<><FileTextOutlined /> 专利基本信息</>}>
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="专利名称">{info.发明名称 || info.patentName || info.title || '-'}</Descriptions.Item>
            <Descriptions.Item label="申请号">{info.申请号 || info.applicationNumber || info.appNumber || '-'}</Descriptions.Item>
            <Descriptions.Item label="申请日">{info.申请日 || info.applicationDate || info.appDate || '-'}</Descriptions.Item>
            <Descriptions.Item label="申请人">{info.申请人 || info.applicant || '-'}</Descriptions.Item>
            <Descriptions.Item label="发明人">{info.发明人 || info.inventor || '-'}</Descriptions.Item>
            <Descriptions.Item label="代理机构">{info.代理机构 || info.agency || '-'}</Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 摘要 */}
        {summary && (
          <Card title={<><RobotOutlined /> 摘要</>}>
            <Paragraph>{summary}</Paragraph>
          </Card>
        )}

        {/* 权利要求书 */}
        {(claims.独立权利要求 || claims.independentClaims || claims.length > 0) && (
          <Card title={<><FileTextOutlined /> 权利要求书</>}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {/* 独立权利要求 */}
              {(claims.独立权利要求 || claims.independentClaims) && (
                <div>
                  <Text strong>独立权利要求：</Text>
                  <List
                    size="small"
                    dataSource={Array.isArray(claims.独立权利要求) ? claims.独立权利要求 : [claims.独立权利要求]}
                    renderItem={(item: any, index: number) => (
                      <List.Item>
                        <Card size="small" style={{ width: '100%', background: '#f0f5ff' }}>
                          <Text strong>权利要求{index + 1}：</Text>
                          <Paragraph style={{ marginBottom: 0 }}>{typeof item === 'string' ? item : item.content || item.text}</Paragraph>
                        </Card>
                      </List.Item>
                    )}
                  />
                </div>
              )}
              
              {/* 从属权利要求 */}
              {(claims.从属权利要求 || claims.dependentClaims) && (
                <div>
                  <Text strong>从属权利要求：</Text>
                  <List
                    size="small"
                    dataSource={Array.isArray(claims.从属权利要求) ? claims.从属权利要求 : [claims.从属权利要求]}
                    renderItem={(item: any, index: number) => (
                      <List.Item>
                        <Card size="small" style={{ width: '100%' }}>
                          <Text>权利要求{index + 2}：</Text>
                          <Paragraph style={{ marginBottom: 0 }}>{typeof item === 'string' ? item : item.content || item.text}</Paragraph>
                        </Card>
                      </List.Item>
                    )}
                  />
                </div>
              )}
            </Space>
          </Card>
        )}

        {/* 说明书结构 */}
        {(description.技术领域 || description.technicalField || description.背景技术 || description.background) && (
          <Card title={<><FileTextOutlined /> 说明书结构</>}>
            <Descriptions column={1} size="small">
              {description.技术领域 || description.technicalField ? (
                <Descriptions.Item label="技术领域">
                  {description.技术领域 || description.technicalField}
                </Descriptions.Item>
              ) : null}
              {description.背景技术 || description.background ? (
                <Descriptions.Item label="背景技术">
                  {description.背景技术 || description.background}
                </Descriptions.Item>
              ) : null}
              {description.发明内容 || description.inventionContent ? (
                <Descriptions.Item label="发明内容">
                  {description.发明内容 || description.inventionContent}
                </Descriptions.Item>
              ) : null}
              {description.有益效果 || description.beneficialEffect ? (
                <Descriptions.Item label="有益效果">
                  {description.有益效果 || description.beneficialEffect}
                </Descriptions.Item>
              ) : null}
            </Descriptions>
          </Card>
        )}
      </Space>
    );
  };

  // 渲染新颖性分析
  const renderNoveltyAnalysis = (reportData: any) => {
    const analysis = reportData.noveltyAnalysis || reportData.新颖性分析;
    
    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title={<><RobotOutlined /> 新颖性分析</>}>
          <Alert
            type={analysis.结论?.includes('具备') || analysis.conclusion?.includes('yes') ? 'success' : 'warning'}
            message={analysis.结论 || analysis.conclusion || '新颖性分析结果'}
            description={analysis.说明 || analysis.description || ''}
            showIcon
          />
        </Card>

        {/* 逐特征比对 */}
        {(analysis.特征比对 || analysis.featureComparison) && (
          <Card title="特征比对分析">
            <List
              size="small"
              dataSource={Array.isArray(analysis.特征比对) ? analysis.特征比对 : [analysis.特征比对]}
              renderItem={(item: any) => (
                <List.Item>
                  <Card size="small" style={{ width: '100%' }}>
                    <Space>
                      {item.新颖性 === '具备' || item.novelty === 'yes' ? (
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      ) : (
                        <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                      )}
                      <Text>{item.特征 || item.feature}</Text>
                    </Space>
                  </Card>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Space>
    );
  };

  // 渲染创造性分析
  const renderInventivenessAnalysis = (reportData: any) => {
    const analysis = reportData.inventivenessAnalysis || reportData.创造性分析;
    
    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title={<><RobotOutlined /> 创造性分析 (三步法)</>}>
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="最接近现有技术">
              {analysis.最接近现有技术 || analysis.closestPriorArt || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="区别技术特征">
              {analysis.区别技术特征 || analysis.distinctiveFeatures || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="实际解决的技术问题">
              {analysis.技术问题 || analysis.technicalProblem || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="显而易见性判断">
              {analysis.显而易见性 || analysis.obviousness || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创造性结论">
              {analysis.结论 || analysis.conclusion || '-'}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      </Space>
    );
  };

  // 渲染权利要求分析
  const renderClaimsAnalysis = (reportData: any) => {
    const claims = reportData.权利要求 || reportData.claims || [];
    
    return (
      <Card title={<><FileTextOutlined /> 权利要求分析</>}>
        <List
          size="small"
          dataSource={Array.isArray(claims) ? claims : [claims]}
          renderItem={(item: any) => (
            <List.Item>
              <Card size="small" style={{ width: '100%' }}>
                <Paragraph style={{ marginBottom: 0 }}>{item.content || item.text || JSON.stringify(item)}</Paragraph>
              </Card>
            </List.Item>
          )}
        />
      </Card>
    );
  };

  // 渲染通用分析
  const renderGenericAnalysis = (reportData: any) => {
    // 尝试渲染任何JSON对象
    const entries = Object.entries(reportData);
    
    return (
      <Card title={<><RobotOutlined /> 分析报告</>}>
        <Collapse
          items={entries.map(([key, value]: [string, any], index: number) => ({
            key: String(index),
            label: key,
            children: (
              typeof value === 'object' ? (
                <pre style={{ maxHeight: 300, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                  {JSON.stringify(value, null, 2)}
                </pre>
              ) : (
                <Paragraph>{String(value)}</Paragraph>
              )
            )
          }))}
        />
      </Card>
    );
  };

  return (
    <div className="patent-analysis-report">
      {renderStructuredReport()}
    </div>
  );
};

export default PatentAnalysisReport;
