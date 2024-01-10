from pathlib import Path
from shutil import rmtree, copy
import git

from knowledge_repo import KnowledgeRepository
from knowledge_repo.scripts.kr import add as kradd, reindex, repo_app


def prep_tests(quiet: bool = False):
    root = Path(__file__).parent.parent

    tests = root/'tests'
    pkg = root/'knowledge_repo'
    coverage = root/'.coverage'

    db = tests/'knowledge.db'
    test_repo_path = tests/'test_repo'
    config_repo = tests/'config_repo.yml'
    config_server = tests/'config_server.py'
    test_posts = tests/'test_posts'

    test_repo_config = test_repo_path/'.knowledge_repo_config.yml'
    uri = f"git://{test_repo_path}"

    templates = pkg/'templates'

    # clear old test artifacts
    db.unlink(True)
    coverage.unlink(True)

    # create test repo
    if not quiet:
        print(f"Creating a test repository in {test_repo_path}...")

    rmtree(str(test_repo_path), True)
    test_repo_path.mkdir(parents=True, exist_ok=True)

    gitrepo = git.Repo.init(str(test_repo_path), initial_branch='master')
    gitrepo.config_writer().set_value("user", "name", "Knowledge Developer").release()
    gitrepo.config_writer().set_value("user", "email", "knowledge_developer@example.com").release()

    repo = KnowledgeRepository.create_for_uri(uri)
    copy(str(config_repo), str(test_repo_config))

    gitrepo.index.add(str(test_repo_config))
    gitrepo.index.commit("Update repository config.")

    kradd(repo, f'{templates/"knowledge_template.ipynb"}', 'projects/test/ipynb_test', message="Test commit", branch='master')
    kradd(repo, f'{templates/"knowledge_template.Rmd"}', 'projects/test/Rmd_test', message="Test commit", branch='master')
    kradd(repo, f'{templates/"knowledge_template.md"}', 'projects/test/md_test', message="Test commit", branch='master')

    for post in test_posts.iterdir():
        if post.suffix in ('.ipynb', '.Rmd', '.md', '.org'):
            kradd(repo, str(post), f'projects/{post.name}', message="Test commit", branch='master')

    if not quiet:
        print(
            "\n"
            "Synchronising database index\n"
            "-----------------------------\n"
            '\n'
        )

    app = repo_app(repo, config=str(config_server))
    reindex(app)
    gitrepo.close()
    del gitrepo
    del repo


if __name__ == '__main__':
    prep_tests()
