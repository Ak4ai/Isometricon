import pytest
from src.core.game_storage import Preferences, WorldLibrary, seed_value
from src.interactive.game_menus import GameMenus


def test_seed_text_is_stable_and_numeric_equivalent():
    assert seed_value('floresta') == seed_value('floresta')
    assert seed_value(' 42 ') == 42
    assert 0 <= seed_value('') < 2**31


def test_world_roundtrip_and_bad_file(tmp_path):
    library = WorldLibrary(tmp_path)
    world = library.create('Aventura', 'floresta')
    world.update(position=[1., 9., -3.], played=120, character={'versao': 1})
    library.save(world)
    (tmp_path/'invalid.json').write_text('{')
    assert library.list() == [world]
    assert library.list()[0]['seed'] == seed_value('floresta')
    with pytest.raises(ValueError):
        library.create(' ', '')


def test_preferences_rebinding_persists_and_suppresses_old_key(tmp_path):
    prefs = Preferences(tmp_path/'prefs.json')
    prefs.bind('forward', 73)
    assert prefs.canonical(73) == 87
    assert prefs.canonical(87) == -1
    with pytest.raises(ValueError):
        prefs.bind('backward', 73)
    with pytest.raises(ValueError):
        prefs.bind('forward', 256)
    prefs.save()
    assert Preferences(prefs.path).data == prefs.data


def test_settings_discard_preserves_applied_preferences(tmp_path):
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), WorldLibrary(tmp_path/'worlds'), create_gl=False)
    menus.settings()
    menus.activate('toggle:vsync')
    menus.back()
    assert menus.page == 'discard'
    menus.activate('keep')
    assert menus.draft['vsync'] is False
    menus.activate('apply')
    assert menus.preferences.data['vsync'] is False
    menus.back()
    assert menus.page == 'welcome'


def test_menu_world_selection_and_scaled_hit_testing(tmp_path):
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), WorldLibrary(tmp_path/'worlds'), create_gl=False)
    menus.render(880, 584)
    rect, action = menus.hits[0]
    menus.click((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)
    assert menus.page == 'create'
    menus.fields = {'name': 'Mundo novo', 'seed': '123'}
    menus.activate('create_world')
    assert menus.result[0] == 'play'
    assert menus.result[1]['seed'] == 123
    menus.go('worlds')
    menus.render(880, 584)
    assert any(action.startswith('load:') for _, action in menus.hits)

def test_delete_world_requires_confirmation_and_cannot_recreate_active_save(tmp_path):
    library = WorldLibrary(tmp_path/'worlds')
    world = library.create('Excluir', '123')
    other = library.create('Manter', '456')
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), library, create_gl=False)
    menus.world = world
    menus.go('worlds')
    menus.activate('delete:' + world['id'])
    assert menus.page == 'delete_world'
    assert len(library.list()) == 2
    menus.back()
    assert menus.page == 'worlds'
    assert len(library.list()) == 2
    menus.activate('delete:' + world['id'])
    menus.render(1320, 876)
    assert menus.hits[0][1] == 'cancel_delete'
    menus.activate('confirm_delete')
    assert library.list() == [other]
    assert menus.world is None
    assert menus.page == 'worlds'


def test_delete_rejects_paths_outside_library(tmp_path):
    library = WorldLibrary(tmp_path/'worlds')
    outside = tmp_path/'keep.json'
    outside.write_text('keep')
    with pytest.raises(ValueError):
        library.delete('../keep')
    assert outside.read_text() == 'keep'


def test_world_list_has_separate_load_and_delete_buttons(tmp_path):
    library = WorldLibrary(tmp_path/'worlds')
    world = library.create('Mundo', '123')
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), library, create_gl=False)
    menus.go('worlds')
    menus.render(1280, 720)
    actions = {action: rect for rect, action in menus.hits}
    assert actions['load:' + world['id']][2] < actions['delete:' + world['id']][0]

def test_creation_placeholders_are_not_part_of_entered_text(tmp_path):
    import glfw
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), WorldLibrary(tmp_path/'worlds'), create_gl=False)
    menus.go('create')
    assert menus.fields == {'name': '', 'seed': ''}
    menus.activate('field:name')
    for char in 'Meu Castelo':
        if char == ' ':
            menus.key(glfw.KEY_SPACE, glfw.PRESS)
        menus.char(ord(char))
    assert menus.fields['name'] == 'Meu Castelo'
    menus.activate('field:seed')
    for char in '42':
        menus.char(ord(char))
    menus.activate('create_world')
    assert menus.result[1]['name'] == 'Meu Castelo'
    assert menus.result[1]['seed'] == 42


@pytest.mark.parametrize('exit_action', ['back', 'escape'])
def test_leaving_creation_discards_name_and_seed(tmp_path, exit_action):
    import glfw
    library = WorldLibrary(tmp_path/'worlds')
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), library, create_gl=False)
    menus.go('create')
    menus.fields.update(name='Rascunho', seed='123')
    if exit_action == 'back':
        menus.activate('back')
    else:
        menus.key(glfw.KEY_ESCAPE, glfw.PRESS)
    assert menus.page == 'welcome'
    assert menus.fields == {'name': '', 'seed': ''}
    menus.activate('create')
    assert menus.fields == {'name': '', 'seed': ''}
    assert library.list() == []



def test_mouse_activation_requires_release_over_same_button(tmp_path):
    import glfw
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), WorldLibrary(tmp_path/'worlds'), create_gl=False)
    menus.render(1320,876)
    rect, _ = menus.hits[0]
    x,y=(rect[0]+rect[2])/2,(rect[1]+rect[3])/2
    menus.mouse_button(x,y,glfw.PRESS)
    assert menus.page=='welcome'
    menus.mouse_button(0,0,glfw.RELEASE)
    assert menus.page=='welcome'
    menus.mouse_button(x,y,glfw.PRESS)
    menus.mouse_button(x,y,glfw.RELEASE)
    assert menus.page=='create'


def test_sensitivity_slider_changes_only_draft_until_apply(tmp_path):
    import glfw
    menus = GameMenus('test', Preferences(tmp_path/'prefs.json'), WorldLibrary(tmp_path/'worlds'), create_gl=False)
    menus.settings()
    menus.render(1320,876)
    rect=next(r for r,a in menus.hits if a=='sensitivity')
    y=(rect[1]+rect[3])/2
    menus.mouse_button(rect[2]-186,y,glfw.PRESS)
    menus.hover(rect[2]-70,y)
    menus.mouse_button(rect[2]-70,y,glfw.RELEASE)
    assert menus.draft['sensitivity']==2.
    assert menus.preferences.data['sensitivity']==1.
    menus.activate('apply')
    assert Preferences(menus.preferences.path).data['sensitivity']==2.


def test_delete_removes_world_preview_without_touching_other_saves(tmp_path):
    library=WorldLibrary(tmp_path/'worlds')
    first=library.create('Primeiro','11')
    second=library.create('Segundo','22')
    preview=library.directory/(first['id']+'.png')
    preview.write_bytes(b'preview')
    library.delete(first['id'])
    assert not preview.exists()
    assert library.list()==[second]

def test_gpu_menu_updates_only_changed_controls_and_keeps_texture_correct(tmp_path):
    from types import SimpleNamespace
    from PIL import Image
    import glfw

    class Texture:
        def __init__(self):
            self.image=None
            self.uploads=[]
        def set_image(self,image,*,region=None):
            self.uploads.append(region)
            if region is None:
                self.image=image.copy()
            else:
                self.image.paste(image.crop(region),region[:2])
        def draw(self,*args,**kwargs):
            pass

    menus=GameMenus('test',Preferences(tmp_path/'prefs.json'),WorldLibrary(tmp_path/'worlds'),create_gl=False)
    menus.preferences.data['reduce_motion']=True
    menus.quad=Texture()
    menus.scrim_quad=Texture()
    menus.landscape=SimpleNamespace(prepare=lambda *a:None,draw=lambda *a:None)
    menus.render(1280,720)
    # Assenta o foco inicial; a transição não deve reconstruir a textura por quadro.
    menus.render(1280,720)
    initial_uploads=len(menus.quad.uploads)
    for _ in range(5):
        menus.render(1280,720)
    assert len(menus.quad.uploads)==initial_uploads
    for rect,action in list(menus.hits):
        x,y=(rect[0]+rect[2])/2,(rect[1]+rect[3])/2
        menus.hover(x,y)
        menus.render(1280,720)
        assert menus.quad.image.tobytes()==menus.last_image.tobytes()
    assert any(region is not None for region in menus.quad.uploads)
    rect,_=menus.hits[0]
    x,y=(rect[0]+rect[2])/2,(rect[1]+rect[3])/2
    menus.mouse_button(x,y,glfw.PRESS)
    menus.render(1280,720)
    assert menus.quad.image.tobytes()==menus.last_image.tobytes()
    menus.mouse_button(0,0,glfw.RELEASE)
    menus.render(1280,720)
    assert menus.quad.image.tobytes()==menus.last_image.tobytes()
    menus.go('create')
    menus.render(1280,720)
    assert menus.quad.uploads[-1] is None
