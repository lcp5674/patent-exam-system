<template>
  <div class="crawler-config-page">
    <el-card class="status-card">
      <template #header>
        <div class="card-header">
          <span>爬虫状态</span>
          <el-tag :type="status.is_running ? 'success' : 'info'">
            {{ status.is_running ? '运行中' : '空闲' }}
          </el-tag>
        </div>
      </template>
      
      <div class="status-grid">
        <div class="status-item">
          <span class="label">累计爬取专利：</span>
          <span class="value">{{ status.total_patents || 0 }} 件</span>
        </div>
        <div class="status-item">
          <span class="label">最后同步时间：</span>
          <span class="value">{{ status.last_sync_time ? formatTime(status.last_sync_time) : '未同步' }}</span>
        </div>
      </div>
      
      <!-- 当前运行任务 -->
      <div v-if="status.current_task" class="current-task">
        <h4>当前运行任务</h4>
        <el-progress :percentage="status.current_task.progress.toFixed(1)" :show-text="true" />
        <div class="task-info">
          <span>任务类型：{{ status.current_task.task_type === 'full' ? '全量爬取' : '增量同步' }}</span>
          <span>进度：{{ status.current_task.completed_count }}/{{ status.current_task.total_count }} 件</span>
          <span>开始时间：{{ formatTime(status.current_task.start_time) }}</span>
        </div>
        <el-button type="danger" @click="stopCrawl" size="small">
          停止任务
        </el-button>
      </div>
    </el-card>

    <!-- 全量爬取配置 -->
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span>全量爬取配置</span>
        </div>
      </template>
      
      <el-form :model="fullConfig" label-width="120px">
        <el-form-item label="开始年份">
          <el-input-number v-model="fullConfig.start_year" :min="1985" :max="new Date().getFullYear()" />
        </el-form-item>
        <el-form-item label="结束年份">
          <el-input-number v-model="fullConfig.end_year" :min="1985" :max="new Date().getFullYear()" />
        </el-form-item>
        <el-form-item label="技术领域">
          <el-select v-model="fullConfig.tech_fields" multiple placeholder="请选择技术领域" style="width: 100%">
            <el-option label="电子信息" value="电子信息" />
            <el-option label="人工智能" value="人工智能" />
            <el-option label="生物医药" value="生物医药" />
            <el-option label="机械制造" value="机械制造" />
            <el-option label="化工材料" value="化工材料" />
            <el-option label="新能源" value="新能源" />
            <el-option label="航空航天" value="航空航天" />
            <el-option label="农业技术" value="农业技术" />
            <el-option label="交通运输" value="交通运输" />
            <el-option label="环境保护" value="环境保护" />
          </el-select>
          <div class="tip">不选则爬取所有领域</div>
        </el-form-item>
        <el-form-item label="最大爬取量">
          <el-input-number v-model="fullConfig.max_count" :min="1" placeholder="不限制" />
          <div class="tip">不填则不限制数量</div>
        </el-form-item>
        <el-form-item label="自动向量化">
          <el-switch v-model="fullConfig.auto_vectorize" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="startFullCrawl" :loading="starting">
            启动全量爬取
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 增量爬取配置 -->
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span>增量同步配置</span>
          <el-switch v-model="incrementalConfig.enabled" @change="updateIncrementalConfig" />
        </div>
      </template>
      
      <el-form :model="incrementalConfig" label-width="120px" :disabled="!incrementalConfig.enabled">
        <el-form-item label="同步时间">
          <el-time-picker
            v-model="incrementalConfig.sync_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="选择每日同步时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="同步天数">
          <el-input-number v-model="incrementalConfig.sync_days" :min="1" :max="7" />
          <div class="tip">每次同步前N天的专利数据</div>
        </el-form-item>
        <el-form-item label="自动向量化">
          <el-switch v-model="incrementalConfig.auto_vectorize" />
        </el-form-item>
        <el-form-item label="重试次数">
          <el-input-number v-model="incrementalConfig.retry_count" :min="1" :max="10" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runIncrementalNow" :loading="runningIncremental">
            立即执行一次同步
          </el-button>
          <el-button type="success" @click="saveIncrementalConfig" :loading="saving" style="margin-left: 10px">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务历史 -->
    <el-card class="history-card">
      <template #header>
        <span>爬取任务历史</span>
      </template>
      
      <el-table :data="taskList" border style="width: 100%">
        <el-table-column prop="task_id" label="任务ID" width="120" />
        <el-table-column prop="task_type" label="任务类型" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.task_type === 'full' ? 'primary' : 'success'">
              {{ scope.row.task_type === 'full' ? '全量爬取' : '增量同步' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="scope">
            {{ scope.row.progress.toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="completed_count" label="完成数量" width="120">
          <template #default="scope">
            {{ scope.row.completed_count }}/{{ scope.row.total_count }}
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" width="180">
          <template #default="scope">
            {{ formatTime(scope.row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="end_time" label="结束时间" width="180">
          <template #default="scope">
            {{ scope.row.end_time ? formatTime(scope.row.end_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" show-overflow-tooltip />
      </el-table>
      
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadTaskList"
          @current-change="loadTaskList"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const status = ref({})
const fullConfig = ref({
  start_year: 2020,
  end_year: new Date().getFullYear(),
  tech_fields: [],
  max_count: null,
  auto_vectorize: true
})
const incrementalConfig = ref({
  enabled: true,
  sync_time: '02:00',
  sync_days: 1,
  auto_vectorize: true,
  retry_count: 3
})
const taskList = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const starting = ref(false)
const saving = ref(false)
const runningIncremental = ref(false)

const formatTime = (time) => {
  if (!time) return ''
  return new Date(time).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const map = {
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    pending: 'warning'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    pending: '等待中'
  }
  return map[status] || status
}

const loadStatus = async () => {
  try {
    const res = await api.get('/crawler/status')
    status.value = res.data
    if (res.data.full_crawl_config) {
      fullConfig.value = res.data.full_crawl_config
    }
    if (res.data.incremental_config) {
      incrementalConfig.value = res.data.incremental_config
    }
  } catch (e) {
    ElMessage.error('加载状态失败')
  }
}

const loadTaskList = async () => {
  try {
    const res = await api.get('/crawler/tasks', {
      params: { page: page.value, page_size: pageSize.value }
    })
    taskList.value = res.data
    // 实际项目中需要从header获取total
    total.value = res.headers['x-total-count'] || 100
  } catch (e) {
    ElMessage.error('加载任务列表失败')
  }
}

const startFullCrawl = async () => {
  if (fullConfig.value.start_year > fullConfig.value.end_year) {
    ElMessage.error('开始年份不能大于结束年份')
    return
  }
  
  try {
    starting.value = true
    await api.post('/crawler/full-crawl/start', fullConfig.value)
    ElMessage.success('全量爬取已启动')
    setTimeout(loadStatus, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '启动失败')
  } finally {
    starting.value = false
  }
}

const stopCrawl = async () => {
  try {
    await ElMessageBox.confirm('确定要停止当前爬取任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.post('/crawler/full-crawl/stop')
    ElMessage.success('任务已停止')
    setTimeout(loadStatus, 1000)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('停止失败')
    }
  }
}

const saveIncrementalConfig = async () => {
  try {
    saving.value = true
    await api.put('/crawler/incremental/config', incrementalConfig.value)
    ElMessage.success('配置已保存')
    setTimeout(loadStatus, 1000)
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const updateIncrementalConfig = async () => {
  await saveIncrementalConfig()
}

const runIncrementalNow = async () => {
  try {
    runningIncremental.value = true
    await api.post('/crawler/incremental/run-now')
    ElMessage.success('增量同步已启动')
    setTimeout(loadStatus, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '启动失败')
  } finally {
    runningIncremental.value = false
  }
}

onMounted(() => {
  loadStatus()
  loadTaskList()
  
  // 每隔30秒刷新一次状态
  setInterval(loadStatus, 30000)
})
</script>

<style scoped>
.crawler-config-page {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-card, .config-card, .history-card {
  margin-bottom: 20px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 10px;
  margin-bottom: 20px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.status-item .label {
  color: #606266;
}

.status-item .value {
  font-weight: 500;
}

.current-task {
  padding: 15px;
  background: #ecf5ff;
  border-radius: 4px;
}

.current-task h4 {
  margin: 0 0 15px 0;
  color: #409eff;
}

.task-info {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin: 15px 0;
  font-size: 14px;
}

.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}
</style>
