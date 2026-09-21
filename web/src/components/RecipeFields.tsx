import type {Recipe,RecipeParameters} from '../api/recipes'

export function RecipeFields({recipe,values,onChange}:{recipe:Recipe;values:RecipeParameters;onChange:(values:RecipeParameters)=>void}){
  return <>{Object.entries(recipe.parameters.properties).map(([name,field])=>{
    const id=`recipe-${name}`
    const options=field.enum??(field.const!==undefined?[field.const]:undefined)
    const update=(value:string)=>onChange({...values,[name]:field.type==='integer'?Number(value):value})
    return <div className="field" key={name}><label htmlFor={id}>{field.title}</label>{options?
      <select id={id} value={values[name]??field.default} disabled={field.const!==undefined} onChange={event=>update(event.target.value)}>{options.map(value=><option key={value} value={value}>{value==='zh'?'中文':value==='en'?'English':value}</option>)}</select>:
      <input id={id} required type={field.type==='integer'?'number':'text'} step={field.type==='integer'?1:undefined} min={field.minimum} max={field.maximum} value={values[name]??field.default} onChange={event=>update(event.target.value)}/>}
    </div>
  })}</>
}
