from gtmcore.workflows.gitworkflows_utils import handle_git_feedback


class TestGitWorkflowsUtils(object):
    def test_handle_git_feedback_first_msg(self):
        current_feedback = ""
        message = "my first message"

        output = handle_git_feedback(current_feedback, message)

        assert output == "my first message"

    def test_handle_git_feedback_append(self):
        current_feedback = ""
        msg1 = "my first message"
        msg2 = "my second message"

        current_feedback = handle_git_feedback(current_feedback, msg1)
        assert current_feedback == "my first message"
        current_feedback = handle_git_feedback(current_feedback, msg2)
        assert current_feedback == "my first message\nmy second message"

    def test_handle_git_feedback_skip(self):
        current_feedback = ""
        msg1 = "my first message"
        msg2 = "Locking support detected on remote"
        msg3 = ".git/info/lfs.locksverify true"
        msg4 = "hint: asdfasdf"
        msg5 = "my second message"

        current_feedback = handle_git_feedback(current_feedback, msg1)
        assert current_feedback == "my first message"
        current_feedback = handle_git_feedback(current_feedback, msg2)
        assert current_feedback == "my first message"
        current_feedback = handle_git_feedback(current_feedback, msg3)
        assert current_feedback == "my first message"
        current_feedback = handle_git_feedback(current_feedback, msg4)
        assert current_feedback == "my first message"
        current_feedback = handle_git_feedback(current_feedback, msg5)
        assert current_feedback == "my first message\nmy second message"

    def test_handle_git_feedback_update(self):
        current_feedback = ""
        msg1 = "my first message"
        msg2 = "my second message"
        msg3 = "progress: 1"
        msg4 = "progress: 2"
        msg5 = "progress: 3"
        msg6 = "my last message"

        current_feedback = handle_git_feedback(current_feedback, msg1)
        assert current_feedback == "my first message"
        current_feedback = handle_git_feedback(current_feedback, msg2)
        assert current_feedback == "my first message\nmy second message"
        current_feedback = handle_git_feedback(current_feedback, msg3)
        assert current_feedback == "my first message\nmy second message\nprogress: 1"
        current_feedback = handle_git_feedback(current_feedback, msg4)
        assert current_feedback == "my first message\nmy second message\nprogress: 2"
        current_feedback = handle_git_feedback(current_feedback, msg5)
        assert current_feedback == "my first message\nmy second message\nprogress: 3"
        current_feedback = handle_git_feedback(current_feedback, msg6)
        assert current_feedback == "my first message\nmy second message\nprogress: 3\nmy last message"


