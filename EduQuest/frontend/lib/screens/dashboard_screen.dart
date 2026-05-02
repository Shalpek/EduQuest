import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'ai_tutor_screen.dart';
import 'lesson_screen.dart';
import 'login_screen.dart';

class DashboardScreen extends StatefulWidget {
  final int userId;

  const DashboardScreen({required this.userId, super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  static const _destinations = [
    ShellDestination(label: 'Home', icon: Icons.home_outlined),
    ShellDestination(label: 'Learn', icon: Icons.library_books_outlined),
    ShellDestination(label: 'Practice', icon: Icons.quiz_outlined),
    ShellDestination(label: 'Progress', icon: Icons.insights_outlined),
    ShellDestination(label: 'Profile', icon: Icons.person_outline),
  ];

  int _selectedIndex = 0;
  Map<String, dynamic>? profile;
  Map<String, dynamic>? currentUser;
  List<dynamic> courses = [];
  List<dynamic> attempts = [];
  bool isLoading = true;
  String? loadError;

  int get _completedLessonsCount =>
      (profile?['completed_lessons'] as List<dynamic>? ?? []).length;

  double get _averageScore {
    if (attempts.isEmpty) return 0;
    final total = attempts.fold<double>(
      0,
      (sum, item) => sum + ((item['score'] ?? 0) as num).toDouble(),
    );
    return total / attempts.length;
  }

  int get _passedAttempts {
    return attempts
        .where((item) => (((item['score'] ?? 0) as num).toDouble()) >= 0.7)
        .length;
  }

  int get _level => ((profile?['level'] ?? 1) as num).toInt();
  int get _xp => ((profile?['xp'] ?? 0) as num).toInt();
  int get _streak => ((profile?['streak'] ?? 0) as num).toInt();

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      isLoading = true;
      loadError = null;
    });

    try {
      final results = await Future.wait([
        ApiService.getProfile(widget.userId),
        ApiService.getCourses(),
        ApiService.getUserAttempts(widget.userId),
        ApiService.getCurrentUser(),
      ]);

      if (!mounted) return;

      final profileData = results[0] as Map<String, dynamic>?;
      final coursesData = results[1] as List<dynamic>;
      final attemptsData = results[2] as List<dynamic>;
      final currentUserData = results[3] as Map<String, dynamic>?;

      setState(() {
        profile =
            profileData ??
            {'xp': 0, 'level': 1, 'streak': 0, 'completed_lessons': []};
        currentUser =
            currentUserData ??
            {
              'id': widget.userId,
              'full_name': 'Student',
              'email': 'student@eduquest.com',
              'role': 'student',
              'is_active': true,
            };
        courses = coursesData;
        attempts = attemptsData;
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
        loadError =
            'The student dashboard could not load data from the local API.';
      });
    }
  }

  Future<void> _logout() async {
    await ApiService.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  Future<void> _showEditNameDialog() async {
    final controller = TextEditingController(
      text: currentUser?['full_name']?.toString() ?? '',
    );
    final messenger = ScaffoldMessenger.of(context);
    await showAppModalSheet<void>(
      context: context,
      builder: (sheetContext) {
        final navigator = Navigator.of(sheetContext);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Update display name',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Keep your learner profile aligned with the role-aware account shell.',
              style: Theme.of(sheetContext).textTheme.bodySmall,
            ),
            const SizedBox(height: 18),
            TextField(
              controller: controller,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Full name'),
            ),
            const SizedBox(height: 18),
            AdaptiveTwoPane(
              collapseWidth: 360,
              first: OutlinedButton(
                onPressed: () => navigator.pop(),
                child: const Text('Cancel'),
              ),
              second: ElevatedButton(
                onPressed: () async {
                  final name = controller.text.trim();
                  if (name.isEmpty) return;
                  final ok = await ApiService.updateCurrentUser(name);
                  if (!mounted) return;
                  navigator.pop();
                  if (ok) {
                    await _loadData();
                    messenger.showSnackBar(
                      const SnackBar(content: Text('Display name updated')),
                    );
                  }
                },
                child: const Text('Save'),
              ),
            ),
          ],
        );
      },
    );
  }

  Future<void> _showChangePasswordDialog() async {
    final currentController = TextEditingController();
    final newController = TextEditingController();
    final confirmController = TextEditingController();
    final messenger = ScaffoldMessenger.of(context);

    await showAppModalSheet<void>(
      context: context,
      builder: (sheetContext) {
        final navigator = Navigator.of(sheetContext);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Change password',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Use a keyboard-safe sheet instead of a cramped dialog on mobile.',
              style: Theme.of(sheetContext).textTheme.bodySmall,
            ),
            const SizedBox(height: 18),
            TextField(
              controller: currentController,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Current password'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: newController,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'New password'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: confirmController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Confirm new password',
              ),
            ),
            const SizedBox(height: 18),
            AdaptiveTwoPane(
              collapseWidth: 360,
              first: OutlinedButton(
                onPressed: () => navigator.pop(),
                child: const Text('Cancel'),
              ),
              second: ElevatedButton(
                onPressed: () async {
                  if (newController.text != confirmController.text) {
                    messenger.showSnackBar(
                      const SnackBar(
                        content: Text(
                          'New password confirmation does not match',
                        ),
                      ),
                    );
                    return;
                  }
                  final error = await ApiService.changePassword(
                    currentController.text,
                    newController.text,
                  );
                  if (!mounted) return;
                  if (error == null) {
                    navigator.pop();
                    messenger.showSnackBar(
                      const SnackBar(
                        content: Text('Password updated successfully'),
                      ),
                    );
                  } else {
                    messenger.showSnackBar(SnackBar(content: Text(error)));
                  }
                },
                child: const Text('Update'),
              ),
            ),
          ],
        );
      },
    );
  }

  void _openCourse(dynamic course) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => LessonScreen(
              courseId: course['id'],
              courseTitle: course['title']?.toString() ?? 'Course',
              userId: widget.userId,
            ),
      ),
    ).then((_) => _loadData());
  }

  void _openAiTutor([String tutorContext = 'General study planning']) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) =>
                AITutorScreen(userId: widget.userId, contextStr: tutorContext),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Loading your learning hub',
          message: 'Syncing progress, courses, and recent practice activity.',
        ),
      );
    }

    if (loadError != null) {
      return Scaffold(
        body: AppErrorState(
          title: 'Dashboard unavailable',
          description: loadError!,
          onRetry: _loadData,
        ),
      );
    }

    return EduQuestShell(
      title: 'Student workspace',
      subtitle: 'Learn, practice, track mastery, and manage your profile.',
      currentIndex: _selectedIndex,
      destinations: _destinations,
      onSelect: (index) => setState(() => _selectedIndex = index),
      actions: [
        IconButton(
          tooltip: 'Refresh',
          onPressed: _loadData,
          icon: const Icon(Icons.refresh),
        ),
      ],
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 220),
        child: KeyedSubtree(
          key: ValueKey(_selectedIndex),
          child: _buildCurrentTab(),
        ),
      ),
    );
  }

  Widget _buildCurrentTab() {
    switch (_selectedIndex) {
      case 1:
        return _buildCoursesTab();
      case 2:
        return _buildPracticeTab();
      case 3:
        return _buildProgressTab();
      case 4:
        return _buildProfileTab();
      default:
        return _buildHomeTab();
    }
  }

  Widget _buildHomeTab() {
    final firstCourse = courses.isNotEmpty ? courses.first : null;
    final name = currentUser?['full_name']?.toString() ?? 'Learner';
    final completionRate =
        courses.isEmpty
            ? 0.0
            : (_completedLessonsCount / (courses.length * 3))
                .clamp(0.0, 1.0)
                .toDouble();

    return ListView(
      children: [
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  const AppInfoChip(
                    label: 'Self-paced',
                    icon: Icons.play_circle_outline,
                  ),
                  AppInfoChip(
                    label: '$_streak day streak',
                    icon: Icons.local_fire_department_outlined,
                    color: EduQuestColors.secondary,
                  ),
                  AppInfoChip(
                    label: 'Level $_level',
                    icon: Icons.stars_outlined,
                    color: EduQuestColors.info,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                'Welcome back, $name',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 10),
              Text(
                'You are building a mastery-driven study routine with visible progress, repeatable practice, and AI-supported explanations.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
              const SizedBox(height: 18),
              LinearProgressIndicator(
                value: completionRate,
                minHeight: 10,
                borderRadius: BorderRadius.circular(999),
                backgroundColor: EduQuestColors.primarySoft,
              ),
              const SizedBox(height: 10),
              Text(
                '${(completionRate * 100).round()}% of your current study path completed',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 18),
              AdaptiveTwoPane(
                first: ElevatedButton.icon(
                  onPressed:
                      firstCourse == null
                          ? null
                          : () => _openCourse(firstCourse),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Continue learning'),
                ),
                second: OutlinedButton.icon(
                  onPressed:
                      () => _openAiTutor(
                        firstCourse?['title']?.toString() ??
                            'Learning strategy',
                      ),
                  icon: const Icon(Icons.smart_toy_outlined),
                  label: const Text('Ask AI coach'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ResponsiveStatsGrid(
          children: [
            AppStatCard(
              label: 'Total XP',
              value: '$_xp',
              icon: Icons.bolt_outlined,
              color: EduQuestColors.primary,
            ),
            AppStatCard(
              label: 'Average score',
              value: '${(_averageScore * 100).round()}%',
              icon: Icons.show_chart,
              color: EduQuestColors.info,
            ),
            AppStatCard(
              label: 'Completed lessons',
              value: '$_completedLessonsCount',
              icon: Icons.task_alt_outlined,
              color: EduQuestColors.success,
            ),
            AppStatCard(
              label: 'Passed quizzes',
              value: '$_passedAttempts',
              icon: Icons.emoji_events_outlined,
              color: EduQuestColors.secondary,
            ),
          ],
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Quick actions',
          subtitle:
              'Move between learning, practice, and review without losing momentum.',
        ),
        const SizedBox(height: 12),
        AdaptiveTwoPane(
          first: AppActionCard(
            title: 'Explore courses',
            subtitle: 'Browse your curriculum and continue structured lessons.',
            icon: Icons.auto_stories_outlined,
            color: EduQuestColors.primary,
            onTap: () => setState(() => _selectedIndex = 1),
          ),
          second: AppActionCard(
            title: 'Practice smarter',
            subtitle:
                'Use review loops, AI explanations, and low-stakes retries.',
            icon: Icons.psychology_alt_outlined,
            color: EduQuestColors.accent,
            onTap: () => setState(() => _selectedIndex = 2),
          ),
        ),
        const SizedBox(height: 16),
        AppSectionHeader(
          title: 'Current path',
          subtitle: 'Your active curriculum and recommended next steps.',
          trailing: TextButton(
            onPressed: () => setState(() => _selectedIndex = 1),
            child: const Text('See all'),
          ),
        ),
        const SizedBox(height: 12),
        if (courses.isEmpty)
          AppEmptyState(
            icon: Icons.library_books_outlined,
            title: 'No courses yet',
            description:
                'The catalog is empty right now. Refresh after seeded course content is expanded.',
            actionLabel: 'Refresh',
            onAction: _loadData,
          )
        else
          ...courses.take(3).map(_buildCourseCard),
      ],
    );
  }

  Widget _buildCoursesTab() {
    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Learning paths',
          subtitle:
              'Explore course cards, continue where you left off, and move into lesson curricula.',
        ),
        const SizedBox(height: 12),
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.search, color: EduQuestColors.textMuted),
              const SizedBox(height: 10),
              Text(
                'Search, level filters, and effort tags will sit here once the catalog metadata is fully populated.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (courses.isEmpty)
          AppEmptyState(
            icon: Icons.school_outlined,
            title: 'Course catalog is empty',
            description:
                'Teacher publishing and richer seeded data will fill this learning path view.',
            actionLabel: 'Refresh',
            onAction: _loadData,
          )
        else
          ...courses.map(_buildCourseCard),
      ],
    );
  }

  Widget _buildPracticeTab() {
    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Practice modes',
          subtitle:
              'Mix lesson review, test-like recall, and AI-guided explanations instead of relying only on timers.',
        ),
        const SizedBox(height: 12),
        AdaptiveTwoPane(
          first: AppActionCard(
            title: 'Learn mode',
            subtitle: 'Revisit lessons with low-pressure guided review.',
            icon: Icons.menu_book_outlined,
            color: EduQuestColors.primary,
            onTap:
                () =>
                    courses.isEmpty ? _loadData() : _openCourse(courses.first),
          ),
          second: AppActionCard(
            title: 'Ask AI tutor',
            subtitle: 'Get help on mistakes, concepts, or study strategy.',
            icon: Icons.smart_toy_outlined,
            color: EduQuestColors.info,
            onTap: () => _openAiTutor('Quiz review and study support'),
          ),
        ),
        const SizedBox(height: 16),
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Targeted review loop',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Use retries to reinforce recall, then review incorrect answers with AI explanations. This mirrors the thesis goal of meaningful challenge rather than pure speed competition.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: const [
                  AppInfoChip(
                    label: 'Retry-friendly',
                    color: EduQuestColors.success,
                    icon: Icons.replay,
                  ),
                  AppInfoChip(
                    label: 'Immediate feedback',
                    color: EduQuestColors.secondary,
                    icon: Icons.bolt_outlined,
                  ),
                  AppInfoChip(
                    label: 'AI explanations',
                    color: EduQuestColors.info,
                    icon: Icons.record_voice_over_outlined,
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Recent performance',
          subtitle:
              'Track practice history and quickly identify what still needs review.',
        ),
        const SizedBox(height: 12),
        if (attempts.isEmpty)
          const AppEmptyState(
            icon: Icons.history_toggle_off_outlined,
            title: 'No practice attempts yet',
            description:
                'Once you complete quizzes, this area will surface your recent results and review opportunities.',
          )
        else
          ...attempts.take(6).map((attempt) => _buildAttemptCard(attempt)),
      ],
    );
  }

  Widget _buildProgressTab() {
    final completionRatio =
        courses.isEmpty
            ? 0.0
            : (_completedLessonsCount / (courses.length * 3))
                .clamp(0.0, 1.0)
                .toDouble();

    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Mastery and momentum',
          subtitle:
              'Visible progress, repeated practice, and feedback-oriented challenge.',
        ),
        const SizedBox(height: 12),
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(18),
                      color: EduQuestColors.primarySoft,
                    ),
                    child: const Icon(Icons.insights_outlined),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Level $_level learner',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '$_xp XP accumulated across lessons, quizzes, and streak-driven practice.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              LinearProgressIndicator(
                value: completionRatio,
                minHeight: 10,
                borderRadius: BorderRadius.circular(999),
                backgroundColor: EduQuestColors.primarySoft,
              ),
              const SizedBox(height: 10),
              Text(
                '${(_averageScore * 100).round()}% average score | $_completedLessonsCount lessons completed | $_passedAttempts passed quizzes',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ResponsiveStatsGrid(
          children: [
            AppStatCard(
              label: 'Daily streak',
              value: '$_streak',
              icon: Icons.local_fire_department_outlined,
              color: EduQuestColors.secondary,
            ),
            AppStatCard(
              label: 'Attempts',
              value: '${attempts.length}',
              icon: Icons.fact_check_outlined,
              color: EduQuestColors.info,
            ),
            AppStatCard(
              label: 'Completion',
              value: '${(completionRatio * 100).round()}%',
              icon: Icons.rocket_launch_outlined,
              color: EduQuestColors.success,
            ),
            AppStatCard(
              label: 'Courses active',
              value: '${courses.length}',
              icon: Icons.layers_outlined,
              color: EduQuestColors.accent,
            ),
          ],
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Recent activity',
          subtitle: 'A timeline of study events and quiz completions.',
        ),
        const SizedBox(height: 12),
        if (attempts.isEmpty)
          const AppEmptyState(
            icon: Icons.timeline_outlined,
            title: 'No activity timeline yet',
            description:
                'As new attempts land, this timeline will reflect the richer study history and quiz outcomes.',
          )
        else
          ...attempts.take(8).map((attempt) => _buildTimelineItem(attempt)),
      ],
    );
  }

  Widget _buildProfileTab() {
    return ListView(
      children: [
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 30,
                    backgroundColor: EduQuestColors.primarySoft,
                    child: Text(
                      (currentUser?['full_name']?.toString().isNotEmpty ??
                              false)
                          ? currentUser!['full_name']
                              .toString()
                              .trim()
                              .split(' ')
                              .map((part) => part[0])
                              .take(2)
                              .join()
                          : 'ST',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 18,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          currentUser?['full_name']?.toString() ?? 'Student',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          currentUser?['email']?.toString() ??
                              'student@eduquest.com',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  const AppInfoChip(
                    label: 'Student',
                    icon: Icons.school_outlined,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              const Divider(),
              const SizedBox(height: 18),
              Text(
                'Learning summary',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  _buildMiniMetric('XP', '$_xp'),
                  _buildMiniMetric('Level', '$_level'),
                  _buildMiniMetric('Streak', '$_streak days'),
                  _buildMiniMetric(
                    'Avg score',
                    '${(_averageScore * 100).round()}%',
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Account and settings',
          subtitle: 'Manage profile details, credentials, and current session.',
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Edit display name',
          subtitle: 'Keep your learner profile and identity card current.',
          icon: Icons.edit_outlined,
          color: EduQuestColors.primary,
          onTap: _showEditNameDialog,
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Change password',
          subtitle:
              'Update account credentials for this local MVP environment.',
          icon: Icons.lock_reset_outlined,
          color: EduQuestColors.secondary,
          onTap: _showChangePasswordDialog,
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Refresh profile data',
          subtitle: 'Re-sync progress, attempts, and role-aware account data.',
          icon: Icons.refresh_outlined,
          color: EduQuestColors.info,
          onTap: () async {
            await _loadData();
            if (!mounted) return;
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(const SnackBar(content: Text('Profile refreshed')));
          },
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Sign out',
          subtitle:
              'Exit the current student session and return to role selection.',
          icon: Icons.logout_outlined,
          color: EduQuestColors.danger,
          onTap: _logout,
        ),
      ],
    );
  }

  Widget _buildCourseCard(dynamic course) {
    final int id = (course['id'] as num?)?.toInt() ?? 0;
    final progressSeed = (id % 4 + 1) / 5;
    final title = course['title']?.toString() ?? 'Course';
    final description =
        course['description']?.toString() ??
        'Structured curriculum with lessons, quizzes, and repeatable practice.';

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(24),
        onTap: () => _openCourse(course),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    AppInfoChip(
                      label:
                          '${course['lesson_count'] ?? 0} lessons • ${course['quiz_count'] ?? 0} quizzes',
                      color: EduQuestColors.primary,
                      icon: Icons.auto_stories_outlined,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(description, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 14),
                LinearProgressIndicator(
                  value: progressSeed,
                  minHeight: 8,
                  borderRadius: BorderRadius.circular(999),
                  backgroundColor: EduQuestColors.primarySoft,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    Text(
                      '${(progressSeed * 100).round()}% path visibility',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (course['difficulty'] != null)
                      AppInfoChip(
                        label: course['difficulty'].toString(),
                        color: EduQuestColors.info,
                      ),
                    if (course['estimated_effort'] != null)
                      AppInfoChip(
                        label: course['estimated_effort'].toString(),
                        color: EduQuestColors.secondary,
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAttemptCard(dynamic attempt) {
    final score = (((attempt['score'] ?? 0) as num).toDouble() * 100).round();
    final passed = score >= 70;
    final xp = ((attempt['earned_xp'] ?? 0) as num?)?.toInt() ?? 0;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: ListTile(
          contentPadding: const EdgeInsets.all(16),
          leading: CircleAvatar(
            backgroundColor:
                passed
                    ? EduQuestColors.success.withValues(alpha: 0.14)
                    : EduQuestColors.accent.withValues(alpha: 0.14),
            child: Icon(
              passed ? Icons.check_circle_outline : Icons.restart_alt_outlined,
              color: passed ? EduQuestColors.success : EduQuestColors.accent,
            ),
          ),
          title: Text(
            attempt['quiz_title']?.toString() ?? 'Quiz attempt',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              passed
                  ? 'Strong result. Review for retention if needed.'
                  : 'Needs reinforcement. Use retry plus AI explanation.',
            ),
          ),
          trailing: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('$score%', style: Theme.of(context).textTheme.titleMedium),
              Text('+$xp XP', style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTimelineItem(dynamic attempt) {
    final score = (((attempt['score'] ?? 0) as num).toDouble() * 100).round();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppSurface(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 12,
              height: 12,
              margin: const EdgeInsets.only(top: 6),
              decoration: const BoxDecoration(
                color: EduQuestColors.primary,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    attempt['quiz_title']?.toString() ?? 'Quiz attempt',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Scored $score% and earned ${attempt['earned_xp'] ?? 0} XP.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMiniMetric(String label, String value) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: EduQuestColors.bg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: EduQuestColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(label, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
