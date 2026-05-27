import type { App, Plugin } from 'vue'
import { ElAlert } from 'element-plus/es/components/alert/index'
import { ElAside, ElContainer, ElHeader, ElMain } from 'element-plus/es/components/container/index'
import { ElButton } from 'element-plus/es/components/button/index'
import { ElCard } from 'element-plus/es/components/card/index'
import { ElCheckbox } from 'element-plus/es/components/checkbox/index'
import { ElCol } from 'element-plus/es/components/col/index'
import { ElCollapse, ElCollapseItem } from 'element-plus/es/components/collapse/index'
import { ElDatePicker } from 'element-plus/es/components/date-picker/index'
import { ElDescriptions, ElDescriptionsItem } from 'element-plus/es/components/descriptions/index'
import { ElDialog } from 'element-plus/es/components/dialog/index'
import { ElDivider } from 'element-plus/es/components/divider/index'
import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus/es/components/dropdown/index'
import { ElEmpty } from 'element-plus/es/components/empty/index'
import { ElForm, ElFormItem } from 'element-plus/es/components/form/index'
import { ElIcon } from 'element-plus/es/components/icon/index'
import { ElInput } from 'element-plus/es/components/input/index'
import { ElInputNumber } from 'element-plus/es/components/input-number/index'
import { ElLoading } from 'element-plus/es/components/loading/index'
import { ElMenu, ElMenuItem } from 'element-plus/es/components/menu/index'
import { ElOption, ElOptionGroup, ElSelect } from 'element-plus/es/components/select/index'
import { ElPagination } from 'element-plus/es/components/pagination/index'
import { ElProgress } from 'element-plus/es/components/progress/index'
import { ElRadioButton, ElRadioGroup } from 'element-plus/es/components/radio/index'
import { ElRow } from 'element-plus/es/components/row/index'
import { ElSkeleton } from 'element-plus/es/components/skeleton/index'
import { ElStatistic } from 'element-plus/es/components/statistic/index'
import { ElStep, ElSteps } from 'element-plus/es/components/steps/index'
import { ElSwitch } from 'element-plus/es/components/switch/index'
import { ElTable, ElTableColumn } from 'element-plus/es/components/table/index'
import { ElTag } from 'element-plus/es/components/tag/index'
import { ElTooltip } from 'element-plus/es/components/tooltip/index'
import { ElUpload } from 'element-plus/es/components/upload/index'

const plugins: Plugin[] = [
  ElAlert,
  ElAside,
  ElButton,
  ElCard,
  ElCheckbox,
  ElCol,
  ElCollapse,
  ElCollapseItem,
  ElContainer,
  ElDatePicker,
  ElDescriptions,
  ElDescriptionsItem,
  ElDialog,
  ElDivider,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElHeader,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElLoading,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElOptionGroup,
  ElPagination,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSkeleton,
  ElStatistic,
  ElStep,
  ElSteps,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTooltip,
  ElUpload,
]

export function installElementPlus(app: App) {
  for (const plugin of plugins) {
    app.use(plugin)
  }
}
