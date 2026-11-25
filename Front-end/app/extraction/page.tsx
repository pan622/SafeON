import { UploadWorkspace } from "../components/UploadWorkspace";
export default function ExtractionPage() { return <UploadWorkspace mode="extraction" accept=".pdf,.docx" title="知识抽取" description="识别施工文献中的危险因素、因素类型、所属项目与风险等级，输出标准 CSV。" />; }
