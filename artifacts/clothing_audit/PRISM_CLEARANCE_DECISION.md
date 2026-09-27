# Resultado: proteção volumétrica não aprovou o encaixe

Data: 2026-09-27. Experimental; nenhuma substituição do runtime.

## O que foi novo, para não repetir o histórico

Foram revisados RADIAL_SHELL_DECISION.md, WRAP_FRAME_EXPERIMENTS.md,
UNIVERSAL_WRAP_REVIEW.md, CANONICAL_RADIAL_REVIEW.md e SHELL_CLEARANCE_DECISION.md.
Chart blend protege orientação/área da superfície; Poisson reconstrói a superfície;
as auditorias anteriores medem Jacobianos depois da deformação. Nenhum desses
equivale a rejeitar cada movimento do corretor usando o volume entre as cages.

`src/clothing/experimental_prism_constraints.py:PrismShapeConstraints` acrescenta
ao corretor existente limites de determinante, comprimento de arestas e espessura.
O determinante é protegido em 12 amostras por face e nos vínculos da roupa.
Valores inicialmente positivos retêm pelo menos 10%; negativos não podem piorar.
Arestas e espessura ficam entre 0,5 e 2 vezes os valores iniciais. São limites
experimentais nossos, iguais para qualquer peça, não parâmetros do Roblox.

## Gate Blocky: reprovado

Mesma camisa, entradas congeladas, vínculo e cage radial anteriores.

| Medida | Antes | Depois |
|---|---:|---:|
| Amostras da roupa dentro do corpo | 1668/5995 (27,82%) | 1523/5995 (25,40%) |
| Arestas normalizadas >3x, máscara histórica | 957 | 1053 |
| Faces com área normalizada <0,1 | 1 | 0 |
| Centros de faces usadas da cage dentro do corpo | 114/595 | 93/595 |
| Determinantes invertidos na grade de 7140 amostras | 334 | 317 |
| Vínculos invertidos, 2269 avaliados | 263 | 261 |

Não surgiram novos vínculos invertidos nas amostras; dois se recuperaram.
Deslocamento máximo da cage: 4,95% da altura corporal. Seams coincidentes
permanecem coincidentes (~4,4e-16). O solver atingiu 20 iterações sem convergir.
O ganho de penetração é pequeno, a distorção piora e os ombros continuam falhando.
Não avançamos esse corretor aos cinco casos femininos após reprovar o gate.

[Comparação em quatro vistas, antes/acima e depois/abaixo](prism_clearance/blocky_133331049150205_garment_comparison.png).
Mesma câmera e escala entre variantes, incluindo o corpo inteiro no enquadramento.
Sem textura, iluminação ou backface culling. As amostras de penetração incluem
vértices e centros de faces, não são percentuais de área visível.

## Evidências e reprodução

- `prism_clearance/blocky_133331049150205.json`: métricas completas e histórico.
- `prism_clearance/FAILURE_WITNESSES.json`: inversões, limites e testemunhos.
- `prism_clearance/MANIFEST_SHA256.json`: entradas e implementação.

```powershell
python scripts/experiment_shell_clearance.py --prism-guard
python scripts/report_shell_clearance.py --prism-guard
```

O guard é amostrado: não certifica validade entre amostras nem injetividade global.
A investigação seguinte substituiu a amostragem por extremos analíticos de cada
prisma, sem repetir os ajustes: ver DEFORMATION_METHOD_REVIEW.md.

Decisão: encerrar esta linha de correção posterior como candidata à integração.
Ela não demonstrou encaixe suficiente. Preservar como diagnóstico, sem novas
varreduras de parâmetros para tentar tornar a mesma falha aceitável.
