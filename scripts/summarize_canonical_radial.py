"""Build a browsable six-case evidence index and input/code fingerprints."""
from pathlib import Path
import hashlib
import html
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_radial_frames import OUT
from scripts.audit_binding_charts import ASSETS
from src.clothing.wrap_layer_fit import read_wrap_layer


def main():
    cases=[('female_'+a,n) for a,n in zip(ASSETS,['Camisa','Jaqueta','Jeans com botas','Vestido','Suéter'])]
    cases.append(('blocky_'+ASSETS[0],'Camisa no R15 Blocky'))
    summary={};sections=[]
    for key,label in cases:
        path=OUT/(key+'.json');d=json.loads(path.read_text(encoding='utf-8'))
        # Scope annotation is metadata, not a recomputation of measurements.
        for name,row in d['variants'].items():
            row['prism_measurement_scope']=('counterfactual volume from production shell; production does not bind with prisms'
                if name=='production' else 'actual prism cells used by this experimental binding')
        path.write_text(json.dumps(d,indent=2),encoding='utf-8')
        summary[key]={name:dict(edges_over_3_normalized=row['distortion']['historical_length_mask']['over_3'],
            faces_under_tenth_area=row['distortion']['area']['under_tenth'],
            penetrating_sample_percent=100*row['penetration']['penetrating_fraction'],
            inverted_bound_prism_vertices=row['binding_jacobians']['inverted_vertices'],
            orientation_proxy=row['distortion']['orientation_disagreements_with_inner_frame'])
            for name,row in d['variants'].items()}
        rows=''.join('<tr><td>'+name+'</td>'+''.join('<td>'+html.escape(str(round(v,3) if isinstance(v,float) else v))+'</td>' for v in values.values())+'</tr>' for name,values in summary[key].items())
        sections.append(f'<section id="{key}"><h2>{label}</h2><p><a href="{key}.json">Métricas completas</a> · <a href="{key}_outputs.npz">Geometria NumPy</a></p>'
            '<table><tr><th>Método</th><th>Arestas &gt;3× / escala</th><th>Área &lt;10%</th><th>Amostras dentro (%)</th><th>Vértices em prisma invertido*</th><th>Orientação divergente**</th></tr>'+rows+'</table>'
            f'<a href="{key}_comparison.png"><img src="{key}_comparison.png" alt="Comparação em quatro vistas: {label}"></a></section>')
    files=set(ROOT.glob('src/clothing/*.py'))
    files.update(ROOT.glob('scripts/*radial*.py'))
    files.update(ROOT.glob('tests/*radial*.py'))
    for name in ['scripts/experiment_dual_cage_prism.py','scripts/test_r15_shirt_transfer.py','scripts/inspect_classic_mannequin_fbx.py',
                 'scripts/radial_validation_metrics.py','assets/models/character_female_clean_apose_stage2.obj',
                 'assets/models/female_cages_apose_stage2.obj','assets/models/roblox_reference_cages.obj',
                 'artifacts/clothing_audit/BlockyCharacter.fbx','artifacts/clothing_audit/BlockyCharacter_OuterCages.obj']:
        files.add(ROOT/name)
    directory=ROOT/'assets/models/clothing'
    for asset in ASSETS:
        obj=next(directory.glob(f'*_{asset}.obj'));rbxm=next(directory.glob(f'*_{asset}.rbxm'))
        files.update((obj,rbxm));metadata=read_wrap_layer(rbxm)
        files.update(directory/'wrap_cages'/f'{metadata[k]}.obj' for k in ['reference_id','cage_id'])
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    (OUT/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Auditoria da deformação radial</title>
<style>body{font:16px system-ui;margin:32px auto;max-width:1380px;padding:0 16px;color:#20252b}img{max-width:100%;border:1px solid #ddd}table{border-collapse:collapse;margin-bottom:16px}td,th{padding:9px;border:1px solid #ccc;text-align:left}section{margin:40px 0}.decision{background:#fff0db;padding:16px}a{color:#164f8d}</style>
<h1>Seis controles — candidata ainda experimental</h1><p class="decision">Rejeitada para integração. A invariância à exportação foi corrigida, mas jeans, vestido, jaqueta e suéter apresentam regressões. A camisa Blocky ainda penetra o corpo.</p>
<p>Linhas das imagens: produção, radial anterior + prisma, candidata canônica + mesmo prisma. Colunas: frente (câmera −Y), lado (+X), costas (+Y), 3/4. Corpo bege, roupa azul. Mesma câmera e escala isotrópica nas três variantes de cada caso; sem textura, luz ou descarte por normal.</p>
<p>Arestas e áreas normalizadas pela mesma escala RMS por caso. Amostras: vértices + centros das faces; contagens não ponderadas por área. Penetração medida nas componentes fechadas do corpo; duas componentes por corpo permanecem abertas. Invisibilidade por câmera não equivale a penetração.</p>
<p>* Em produção, essa coluna é um volume hipotético: o runtime não usa prismas. Nas outras variantes mede o volume efetivamente usado. ** Divergência contra normais transportadas pela cage interna é apenas um indicador, não contagem comprovada de faces invertidas.</p>
<p><a href="../CANONICAL_RADIAL_REVIEW.md">Relatório técnico e reprodução</a> · <a href="BLOCKY_CLEARANCE_WITNESSES.json">Exemplos concretos Blocky</a> · <a href="MANIFEST_SHA256.json">Hashes dos arquivos</a></p>'''+''.join(sections)+'</html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
