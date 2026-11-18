"""A névoa de guerra em nuvens de blocos: o que fica coberto, a animação e a malha."""
from src.rendering.cloud_fog import CELL, CLEARANCE, FLOATS, WINDOW, CloudField
from src.rendering.fog_of_war import AROUND, OFF, REVEAL


def _field(height=8):
    return CloudField(lambda x, z: height)


def test_cobre_tudo_menos_em_volta_do_grupo():
    field = _field()
    field.update(REVEAL, 0.5, 0.5, 0.016)
    assert (0, 0) not in field.cover                       # onde o personagem está
    assert field.cover[(10, 10)] == 1.0                    # longe
    assert len(field.cover) < WINDOW * WINDOW


def test_o_topo_fica_rente_ao_relevo_e_o_fundo_no_chao():
    bottom, top = _field(8).column((5, 5))
    assert bottom <= 7 and 8 + 1 + CLEARANCE <= top <= 8 + 2 + CLEARANCE


def test_revelar_desfaz_animando_e_some():
    field = _field()
    field.explored.reveal(0.5, 0.5)                         # o jogo marca o explorado a cada quadro
    field.update(REVEAL, 0.5, 0.5, 0.016)
    field.explored.reveal(20.5, 0.5)                        # o grupo andou até lá
    field.update(REVEAL, 20.5, 0.5, 0.1)
    cell = (int(20.5 // CELL), 0)
    assert 0.0 < field.cover[cell] < 1.0 and len(field.moving_mesh()) > 0
    for _ in range(20):
        field.update(REVEAL, 20.5, 0.5, 0.1)
    assert cell not in field.cover
    assert (0, 0) not in field.cover                       # o que já foi visto continua aberto


def test_em_volta_fecha_atras():
    field = _field()
    field.update(AROUND, 0.5, 0.5, 0.016)
    for _ in range(20):
        field.update(AROUND, 30.5, 0.5, 0.1)
    assert field.cover.get((0, 0)) == 1.0                  # a névoa voltou onde ele estava
    assert (int(30.5 // CELL), 0) not in field.cover


def test_desligada_limpa_na_hora_e_malha_so_com_faces_de_fora():
    field = _field()
    field.update(REVEAL, 0.5, 0.5, 0.016)
    mesh = field.full_mesh()
    tops = sum(1 for cell, v in field.cover.items() if v >= 1.0)
    assert mesh.shape[1] == FLOATS and len(mesh) // 6 < tops * 5    # nem todos os lados (os de dentro ficam de fora)
    field.update(OFF, 0.5, 0.5, 0.016)
    assert not field.cover and len(field.full_mesh()) == 0


def test_reset_recomeca():
    field = _field()
    field.update(REVEAL, 0.5, 0.5, 0.016)
    field.reset()
    assert not field.cover and field.origin is None


def test_campo_de_distancia_ralo_na_beira_denso_no_miolo():
    field = _field()
    field.update(REVEAL, 0.5, 0.5, 0.016)
    distance = field.distance_map()                         # [iz, ix]
    ox, oz = field.origin
    assert distance.shape == (WINDOW, WINDOW)
    assert distance[0 - oz, 0 - ox] == 0.0                  # onde o personagem está, aberto
    edge = distance[0 - oz, 3 - ox]                         # a primeira nuvem depois do raio aberto
    assert 0.0 < edge < 0.5 and distance[30 - oz, 30 - ox] == 1.0


def test_malha_vetorizada_tem_os_lados_virados_para_fora():
    field = _field()
    field.update(REVEAL, 0.5, 0.5, 0.016)
    mesh = field.full_mesh()
    below = mesh[:, 5]
    assert below.min() == 0.0 and below.max() > 0.0       # o topo (0) e o pé dos lados (abaixo do topo)
    tops = mesh[mesh[:, 3] == 1.0]
    assert (tops[:, 5] == 0.0).all()
