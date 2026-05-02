import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'ai_tutor_screen.dart';
import 'quiz_screen.dart';

class LessonScreen extends StatefulWidget {
  final int courseId;
  final String courseTitle;
  final int userId;

  const LessonScreen({
    required this.courseId,
    required this.courseTitle,
    required this.userId,
    super.key,
  });

  @override
  State<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends State<LessonScreen> {
  List<dynamic> lessons = [];
  List<int> completedLessons = [];
  dynamic selectedLesson;
  bool isLoading = true;
  String? loadError;

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
      final resLessons = await ApiService.getLessons(widget.courseId);
      final resProfile = await ApiService.getProfile(widget.userId);

      if (!mounted) return;

      setState(() {
        lessons = resLessons;
        completedLessons = List<int>.from(
          resProfile?['completed_lessons'] as List? ?? [],
        );
        selectedLesson = resLessons.isNotEmpty ? resLessons.first : null;
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
        loadError = 'The lesson curriculum could not be loaded.';
      });
    }
  }

  Future<void> _selectLesson(dynamic lesson) async {
    if (!completedLessons.contains(lesson['id'])) {
      await ApiService.completeLesson(widget.userId, lesson['id']);
      if (mounted) {
        setState(() {
          completedLessons = [...completedLessons, lesson['id']];
        });
      }
    }

    setState(() {
      selectedLesson = lesson;
    });
  }

  void _openAiTutor() {
    if (selectedLesson == null) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => AITutorScreen(
              userId: widget.userId,
              contextStr: selectedLesson['title']?.toString() ?? 'Lesson',
            ),
      ),
    );
  }

  Future<void> _openQuiz() async {
    if (selectedLesson == null) return;
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => QuizScreen(
              lessonId: selectedLesson['id'],
              lessonTitle: selectedLesson['title']?.toString() ?? 'Lesson',
              userId: widget.userId,
            ),
      ),
    );
    _loadData();
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Loading curriculum',
          message:
              'Preparing lessons, completion state, and next study actions.',
        ),
      );
    }

    if (loadError != null) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.courseTitle)),
        body: AppErrorState(
          title: 'Course content unavailable',
          description: loadError!,
          onRetry: _loadData,
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text(widget.courseTitle)),
      body:
          lessons.isEmpty
              ? const AppEmptyState(
                icon: Icons.auto_stories_outlined,
                title: 'No lessons published',
                description:
                    'This curriculum screen is ready, but no lessons are attached to the selected course yet.',
              )
              : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildCourseHero(),
                  const SizedBox(height: 16),
                  const AppSectionHeader(
                    title: 'Curriculum',
                    subtitle:
                        'Review lessons, mark reading progress, and jump into AI help or quizzes.',
                  ),
                  const SizedBox(height: 12),
                  ...lessons.map(_buildLessonTile),
                  const SizedBox(height: 16),
                  if (selectedLesson != null) _buildLessonDetails(),
                ],
              ),
    );
  }

  Widget _buildCourseHero() {
    final completed = completedLessons.length;
    final progress = lessons.isEmpty ? 0.0 : completed / lessons.length;

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              const AppInfoChip(
                label: 'Lesson-by-lesson',
                icon: Icons.view_agenda_outlined,
              ),
              AppInfoChip(
                label: '$completed/${lessons.length} completed',
                color: EduQuestColors.secondary,
                icon: Icons.task_alt_outlined,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            widget.courseTitle,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'A phone-first curriculum view with clear sequencing, immediate next actions, and AI-supported study assistance.',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            value: progress,
            minHeight: 10,
            borderRadius: BorderRadius.circular(999),
            backgroundColor: EduQuestColors.primarySoft,
          ),
          const SizedBox(height: 8),
          Text(
            '${(progress * 100).round()}% of course lessons opened or completed',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _buildLessonTile(dynamic lesson) {
    final isSelected = selectedLesson?['id'] == lesson['id'];
    final isCompleted = completedLessons.contains(lesson['id']);

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(24),
        onTap: () => _selectLesson(lesson),
        child: Card(
          color:
              isSelected
                  ? EduQuestColors.surfaceAlt
                  : isCompleted
                  ? EduQuestColors.surface
                  : null,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor:
                      isCompleted
                          ? EduQuestColors.success.withValues(alpha: 0.14)
                          : EduQuestColors.primarySoft,
                  child:
                      isCompleted
                          ? const Icon(
                            Icons.check,
                            color: EduQuestColors.success,
                          )
                          : Text(
                            '${lessons.indexOf(lesson) + 1}',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        lesson['title']?.toString() ?? 'Lesson',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        isCompleted
                            ? '${lesson['estimated_minutes'] ?? 15} min • opened and tracked'
                            : '${lesson['estimated_minutes'] ?? 15} min • tap to continue study',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                Icon(
                  isSelected
                      ? Icons.keyboard_arrow_up
                      : Icons.arrow_forward_ios,
                  color: EduQuestColors.textMuted,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLessonDetails() {
    final lesson = selectedLesson;

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AppSectionHeader(
            title: lesson['title']?.toString() ?? 'Lesson',
            subtitle:
                'Read the lesson, ask for help, then move into quiz practice.',
            trailing: const AppInfoChip(
              label: 'Current lesson',
              color: EduQuestColors.info,
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: EduQuestColors.bg,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: EduQuestColors.border),
            ),
            child: Text(
              lesson['content']?.toString() ??
                  'Lesson material is unavailable right now.',
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
            ),
          ),
          const SizedBox(height: 18),
          AdaptiveTwoPane(
            first: OutlinedButton.icon(
              onPressed: _openAiTutor,
              icon: const Icon(Icons.smart_toy_outlined),
              label: const Text('Ask AI tutor'),
            ),
            second: ElevatedButton.icon(
              onPressed: _openQuiz,
              icon: const Icon(Icons.quiz_outlined),
              label: const Text('Take quiz'),
            ),
          ),
        ],
      ),
    );
  }
}
