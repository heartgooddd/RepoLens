import {request} from './projects'

export interface ParameterField {
  title: string; type: 'string' | 'integer'; default: string | number;
  const?: string | number; enum?: (string | number)[]; minimum?: number; maximum?: number;
}
export interface Recipe {
  id: string; version: string; name: string; verification: string;
  parameters: {properties: Record<string,ParameterField>};
  entry: {path:string; upstream:string; commit:string};
  input: {commit:string|null; read_only:boolean}; requires_model:boolean;
  environment: {runtime:string; dependencies:string; ready:boolean};
  working_directory:string; timeout_seconds:number;
  isolation:{kind:string; available:boolean; reason:string|null};
  ready:boolean; unavailable_reasons:string[];
  artifacts:{root:string; required:string[]};
}
export type RecipeParameters = Record<string,string|number>
export const getRecipes=(signal?:AbortSignal)=>request<{items:Recipe[]}>('/recipes',{signal})
export const defaults=(recipe:Recipe):RecipeParameters=>Object.fromEntries(Object.entries(recipe.parameters.properties).map(([name,field])=>[name,field.default]))
export const createRecipeRun=(recipe_id:string,snapshot_id:string,parameters:RecipeParameters)=>request<import('./runs').Run>('/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipe_id,snapshot_id,parameters})})
