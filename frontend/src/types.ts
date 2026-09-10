export type RiskLevel = "low" | "caution" | "danger" | "emergency";
export interface CaseItem { id:number; title:string; category:string; risk_level:RiskLevel; risk_score:number; based_law:string[]; created_at:string; updated_at:string }
export interface Message { id?:number; case_id:number; role:"assistant"|"user"; content:string; created_at?:string }
export interface Assessment { level:RiskLevel; score:number; category:string; rationale:string; actions:string[]; based_law:string[] }
export interface Attachment { id:number; case_id:number; filename:string; content_type:string; size:number; created_at:string }

