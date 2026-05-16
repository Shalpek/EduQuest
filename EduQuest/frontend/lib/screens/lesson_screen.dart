import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'ai_tutor_screen.dart';
import 'quiz_screen.dart';

class LessonScreen extends StatefulWidget {
  final int courseId;
  final String courseTitle;
  final String? courseDescription;
  final int userId;
  final dynamic initialLesson;
  final bool detailOnly;

  const LessonScreen({
    required this.courseId,
    required this.courseTitle,
    this.courseDescription,
    required this.userId,
    this.initialLesson,
    this.detailOnly = false,
    super.key,
  });

  @override
  State<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends State<LessonScreen> {
  List<dynamic> lessons = [];
  List<int> completedLessons = [];
  Map<int, Map<String, dynamic>> lessonProgress = {};
  Map<String, dynamic>? courseProgressSummary;
  dynamic selectedLesson;
  final Map<int, int> _practiceSelections = {};
  final Map<int, bool> _practiceChecked = {};
  final Map<int, Set<int>> _revealedFlashcards = {};
  final ScrollController _detailScrollController = ScrollController();
  final GlobalKey _quizCtaKey = GlobalKey();
  bool isLoading = true;
  String? loadError;

  @override
  void initState() {
    super.initState();
    selectedLesson = widget.initialLesson;
    _loadData();
  }

  @override
  void dispose() {
    _detailScrollController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    final selectedId = (selectedLesson?['id'] as num?)?.toInt();
    setState(() {
      isLoading = true;
      loadError = null;
    });

    try {
      final results = await Future.wait([
        ApiService.getLessons(widget.courseId),
        ApiService.getProfile(widget.userId),
        ApiService.getCourseProgress(widget.courseId),
      ]);

      if (!mounted) return;
      final resLessons = results[0] as List<dynamic>;
      final resProfile = results[1] as Map<String, dynamic>?;
      final resCourseProgress = results[2] as Map<String, dynamic>?;

      dynamic nextSelected;
      if (selectedId != null) {
        for (final lesson in resLessons) {
          if ((lesson['id'] as num?)?.toInt() == selectedId) {
            nextSelected = lesson;
            break;
          }
        }
      }

      final progressByLesson = <int, Map<String, dynamic>>{};
      final lessonProgressItems =
          resCourseProgress?['lessons'] as List<dynamic>? ?? const [];
      for (final item in lessonProgressItems) {
        if (item is Map<String, dynamic> && item['lesson_id'] is num) {
          progressByLesson[(item['lesson_id'] as num).toInt()] = item;
        }
      }

      setState(() {
        lessons = resLessons;
        completedLessons = List<int>.from(
          resProfile?['completed_lessons'] as List? ?? [],
        );
        lessonProgress = progressByLesson;
        courseProgressSummary =
            resCourseProgress?['summary'] as Map<String, dynamic>?;
        selectedLesson =
            nextSelected ?? (resLessons.isNotEmpty ? resLessons.first : null);
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
    await _openLessonDetail(lesson);
  }

  Future<void> _openLessonDetail(dynamic lesson) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => LessonScreen(
              courseId: widget.courseId,
              courseTitle: widget.courseTitle,
              courseDescription: widget.courseDescription,
              userId: widget.userId,
              initialLesson: lesson,
              detailOnly: true,
            ),
      ),
    );
    if (mounted && !widget.detailOnly) {
      _loadData();
    }
  }

  Future<void> _scrollToQuizCta() async {
    final targetContext = _quizCtaKey.currentContext;
    if (targetContext == null) return;
    await Scrollable.ensureVisible(
      targetContext,
      duration: const Duration(milliseconds: 420),
      curve: Curves.easeOutCubic,
      alignment: 0.25,
    );
  }

  void _openAiTutor([String? promptContext]) {
    if (selectedLesson == null) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => AITutorScreen(
              courseId: widget.courseId,
              courseTitle: widget.courseTitle,
              lessonId: (selectedLesson['id'] as num).toInt(),
              lessonTitle: selectedLesson['title']?.toString() ?? 'Lesson',
              userId: widget.userId,
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

    if (widget.detailOnly) {
      return Scaffold(
        appBar: AppBar(
          title: Text(selectedLesson?['title']?.toString() ?? 'Lesson'),
        ),
        body:
            selectedLesson == null
                ? const AppEmptyState(
                  icon: Icons.auto_stories_outlined,
                  title: 'Lesson unavailable',
                  description:
                      'This lesson could not be loaded. Return to the course and try again.',
                )
                : ListView(
                  controller: _detailScrollController,
                  padding: const EdgeInsets.all(16),
                  children: [
                    _buildLessonDetails(),
                  ],
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
                        'Open a lesson, work through practice, then submit a quiz to save progress.',
                  ),
                  const SizedBox(height: 12),
                  ...lessons.map(_buildLessonTile),
                  const SizedBox(height: 16),
                  _buildNextLessonPreview(),
                ],
              ),
    );
  }

  Widget _buildCourseHero() {
    final completed = ((courseProgressSummary?['completed_lessons'] ?? _completedCourseLessonsCount()) as num).toInt();
    final completionPercent = ((courseProgressSummary?['completion_percent'] ?? (lessons.isEmpty ? 0 : (completed / lessons.length) * 100)) as num).toDouble();
    final progress = (completionPercent / 100).clamp(0.0, 1.0);
    final passedQuizzes = ((courseProgressSummary?['passed_quizzes'] ?? 0) as num).toInt();
    final attemptedQuizzes = ((courseProgressSummary?['attempted_quizzes'] ?? 0) as num).toInt();
    final totalQuizzes = ((courseProgressSummary?['total_quizzes'] ?? 0) as num).toInt();
    final nextLesson = _nextLesson();

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
            widget.courseDescription?.trim().isNotEmpty == true
                ? widget.courseDescription!.trim()
                : 'Study each lesson as a guided sequence: concepts, examples, mini practice, and a saved quiz attempt.',
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
            '${completionPercent.round()}% completed · $passedQuizzes/$totalQuizzes quizzes passed · $attemptedQuizzes attempted',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (nextLesson != null) ...[
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () => _openLessonDetail(nextLesson),
              icon: const Icon(Icons.play_arrow),
              label: const Text('Continue learning'),
            ),
          ],
        ],
      ),
    );
  }

  int _completedCourseLessonsCount() {
    return lessons
        .where((lesson) => completedLessons.contains(lesson['id']))
        .length;
  }

  dynamic _nextLesson() {
    if (lessons.isEmpty) return null;
    for (final lesson in lessons) {
      final progress = _lessonProgressFor(lesson['id']);
      if (!(progress['lesson_completed'] == true)) return lesson;
    }
    return lessons.first;
  }

  Map<String, dynamic> _lessonProgressFor(dynamic lessonId) {
    if (lessonId is num) {
      return lessonProgress[lessonId.toInt()] ?? const {};
    }
    return const {};
  }

  Widget _buildNextLessonPreview() {
    final nextLesson = _nextLesson();
    if (nextLesson == null) return const SizedBox.shrink();
    final summary =
        nextLesson['summary']?.toString() ??
        'Open this lesson to continue the full learning flow.';

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AppSectionHeader(
            title: 'Next step',
            subtitle:
                'Course overview stays focused. Open the lesson page for cards, flashcards, practice, and quiz.',
            trailing: AppInfoChip(
              label:
                  completedLessons.contains(nextLesson['id'])
                      ? 'Review'
                      : 'Recommended',
              color: EduQuestColors.info,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            nextLesson['title']?.toString() ?? 'Lesson',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(
            summary,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: 14),
          ElevatedButton.icon(
            onPressed: () => _openLessonDetail(nextLesson),
            icon: const Icon(Icons.open_in_new),
            label: const Text('Open lesson page'),
          ),
        ],
      ),
    );
  }

  Widget _buildLessonTile(dynamic lesson) {
    final isSelected =
        widget.detailOnly && selectedLesson?['id'] == lesson['id'];
    final progress = _lessonProgressFor(lesson['id']);
    final isCompleted =
        progress['lesson_completed'] == true ||
        completedLessons.contains(lesson['id']);
    final quizAvailable = progress['quiz_available'] == true;
    final quizPassed = progress['quiz_passed'] == true;
    final quizAttempted = progress['quiz_attempted'] == true;
    final bestScore = progress['best_score'];
    final summary = lesson['summary']?.toString() ?? '';

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
                            ? '${lesson['estimated_minutes'] ?? 15} min - completed'
                            : '${lesson['estimated_minutes'] ?? 15} min - study and practice',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          AppInfoChip(
                            label: isCompleted ? 'Lesson completed' : 'Lesson not completed',
                            color: isCompleted
                                ? EduQuestColors.success
                                : EduQuestColors.info,
                          ),
                          if (quizAvailable)
                            AppInfoChip(
                              label: quizPassed
                                  ? 'Quiz passed'
                                  : quizAttempted
                                  ? 'Quiz attempted'
                                  : 'Quiz not started',
                              color: quizPassed
                                  ? EduQuestColors.secondary
                                  : quizAttempted
                                  ? EduQuestColors.accent
                                  : EduQuestColors.primary,
                            ),
                          if (bestScore is num)
                            AppInfoChip(
                              label: 'Best ${(bestScore.toDouble() * 100).round()}%',
                              color: EduQuestColors.info,
                            ),
                        ],
                      ),
                      if (summary.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(
                          summary,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(
                            context,
                          ).textTheme.bodySmall?.copyWith(color: Colors.white70),
                        ),
                      ],
                    ],
                  ),
                ),
                Icon(
                  Icons.arrow_forward_ios,
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
    final payload = _lessonPayload(lesson);
    final objectives = _asStringList(payload['objectives']);
    final concepts = _asMapList(payload['concepts']);
    final example = _asStringMap(payload['example']);
    final visual = _asStringMap(payload['visual']);
    final visualBlocks = _asMapList(payload['visualBlocks']);
    final didYouKnow = _asStringMap(payload['didYouKnow']);
    final flashcards = _asMapList(payload['flashcards']);
    final mistakes = _asStringList(payload['mistakes']);
    final practice = _asStringMap(payload['practice']);
    final finalChallenge = _asStringMap(payload['finalChallenge']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppSectionHeader(
                title: lesson['title']?.toString() ?? 'Lesson',
                subtitle:
                    'Move through the cards, try the mini practice, then submit the quiz to save progress.',
                trailing: const AppInfoChip(
                  label: 'Learning flow',
                  color: EduQuestColors.info,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                payload['hook']?.toString() ??
                    'Start with the idea, then apply it in practice.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: () => _openAiTutor('lesson hint'),
                icon: const Icon(Icons.smart_toy_outlined),
                label: const Text('Ask AI for hint'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        if (objectives.isNotEmpty)
          _buildListCard(
            title: 'Learning objectives',
            subtitle: 'What you should be able to do after this lesson.',
            icon: Icons.flag_outlined,
            color: EduQuestColors.primary,
            items: objectives,
          ),
        if (concepts.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildConceptCards(concepts),
        ],
        const SizedBox(height: 12),
        _buildTextCard(
          title: 'Main explanation',
          subtitle: 'The core idea in student-friendly language.',
          icon: Icons.menu_book_outlined,
          color: EduQuestColors.info,
          body: payload['explanation']?.toString() ?? '',
        ),
        if (example.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildExampleCard(example),
        ],
        const SizedBox(height: 12),
        _buildVisualLearningSection(visual, visualBlocks),
        if (didYouKnow.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildDidYouKnowCard(didYouKnow),
        ],
        if (mistakes.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildListCard(
            title: 'Common mistakes',
            subtitle: 'Watch for these before you answer.',
            icon: Icons.warning_amber_outlined,
            color: EduQuestColors.accent,
            items: mistakes,
          ),
        ],
        if (flashcards.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildFlashcardsCard(lesson, flashcards),
        ],
        if (practice.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildPracticeCard(lesson, practice),
        ],
        const SizedBox(height: 12),
        _buildTextCard(
          title: 'Recap',
          subtitle: 'What to remember before the quiz.',
          icon: Icons.task_alt_outlined,
          color: EduQuestColors.success,
          body: payload['recap']?.toString() ?? '',
        ),
        if (finalChallenge.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildFinalChallengeCard(finalChallenge),
        ],
        const SizedBox(height: 12),
        KeyedSubtree(
          key: _quizCtaKey,
          child: AppSurface(
            child: AdaptiveTwoPane(
              first: OutlinedButton.icon(
                onPressed: () => _openAiTutor('quiz preparation'),
                icon: const Icon(Icons.smart_toy_outlined),
                label: const Text('Ask AI before quiz'),
              ),
              second: ElevatedButton.icon(
                onPressed: _openQuiz,
                icon: const Icon(Icons.quiz_outlined),
                label: const Text('Take quiz'),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTextCard({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required String body,
  }) {
    if (body.trim().isEmpty) return const SizedBox.shrink();
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(title, subtitle, icon, color),
          const SizedBox(height: 14),
          Text(
            body,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
          ),
        ],
      ),
    );
  }

  Widget _buildListCard({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required List<String> items,
  }) {
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(title, subtitle, icon, color),
          const SizedBox(height: 14),
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.check_circle_outline, size: 18, color: color),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      item,
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConceptCards(List<Map<String, dynamic>> concepts) {
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            'Key concepts',
            'Short cards for the ideas the quiz will reuse.',
            Icons.style_outlined,
            EduQuestColors.secondary,
          ),
          const SizedBox(height: 14),
          ...concepts.map((concept) {
            return Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: EduQuestColors.bg,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: EduQuestColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    concept['title']?.toString() ?? 'Concept',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    concept['body']?.toString() ?? '',
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(color: Colors.white70),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildExampleCard(Map<String, dynamic> example) {
    final body = example['body']?.toString() ?? '';
    final isCode = example['kind']?.toString() == 'code';
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            example['title']?.toString() ?? 'Example',
            isCode
                ? 'Read the code slowly and connect it to the concept.'
                : 'A concrete scenario that makes the idea usable.',
            isCode ? Icons.code : Icons.lightbulb_outline,
            EduQuestColors.primary,
          ),
          const SizedBox(height: 14),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: EduQuestColors.bg,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: EduQuestColors.border),
            ),
            child: Text(
              body,
              style:
                  isCode
                      ? const TextStyle(
                        color: Colors.white70,
                        fontFamily: 'monospace',
                        height: 1.45,
                      )
                      : Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVisualLearningSection(
    Map<String, dynamic> visual,
    List<Map<String, dynamic>> visualBlocks,
  ) {
    final fallbackVisual =
        visual.isNotEmpty
            ? visual
            : {
              'kind': 'concept-map',
              'title': 'Visual model: concept map',
              'body':
                  'Use this visual checkpoint to connect the lesson idea, example, practice task, and quiz.',
            };
    final blocks = visualBlocks;

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            'Visual learning',
            'Diagram-style checkpoints that make abstract ideas easier to scan.',
            Icons.account_tree_outlined,
            EduQuestColors.info,
          ),
          const SizedBox(height: 14),
          _buildVisualDiagram(fallbackVisual),
          const SizedBox(height: 12),
          ...blocks.map(
            (block) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _buildVisualBlock(block),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVisualDiagram(Map<String, dynamic> visual) {
    final steps = _asStringList(visual['steps']);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: EduQuestColors.bg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: EduQuestColors.border),
      ),
      child: Column(
        children: [
          Icon(
            _visualIcon(visual['kind']?.toString()),
            color: EduQuestColors.info,
            size: 42,
          ),
          const SizedBox(height: 12),
          Text(
            visual['title']?.toString() ?? 'Visual model',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 8),
          Text(
            visual['body']?.toString() ??
                'Connect the concept, example, practice, and quiz.',
            textAlign: TextAlign.center,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: Colors.white70),
          ),
          if (steps.isNotEmpty) ...[
            const SizedBox(height: 12),
            _buildStepStrip(steps),
          ],
        ],
      ),
    );
  }

  Widget _buildVisualBlock(Map<String, dynamic> block) {
    final steps = _asStringList(block['steps']);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: EduQuestColors.bg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: EduQuestColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                _visualIcon(block['kind']?.toString()),
                color: EduQuestColors.info,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  block['title']?.toString() ?? 'Visual checkpoint',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            block['body']?.toString() ?? '',
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: Colors.white70),
          ),
          if (steps.isNotEmpty) ...[
            const SizedBox(height: 12),
            _buildStepStrip(steps),
          ],
        ],
      ),
    );
  }

  Widget _buildStepStrip(List<String> steps) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children:
          steps
              .map(
                (step) => AppInfoChip(
                  label: step,
                  color: EduQuestColors.info,
                  icon: Icons.arrow_forward_outlined,
                ),
              )
              .toList(),
    );
  }

  Widget _buildDidYouKnowCard(Map<String, dynamic> didYouKnow) {
    final body = didYouKnow['body']?.toString() ?? '';
    if (body.trim().isEmpty) return const SizedBox.shrink();
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            didYouKnow['title']?.toString() ?? 'Did you know?',
            'A quick memory hook before practice.',
            Icons.lightbulb_outline,
            EduQuestColors.secondary,
          ),
          const SizedBox(height: 14),
          Text(
            body,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
          ),
        ],
      ),
    );
  }

  Widget _buildFlashcardsCard(
    dynamic lesson,
    List<Map<String, dynamic>> flashcards,
  ) {
    final lessonId = (lesson['id'] as num?)?.toInt() ?? 0;
    final revealed = _revealedFlashcards[lessonId] ?? <int>{};
    final reviewedCount = revealed.length.clamp(0, flashcards.length);
    final allRevealed =
        flashcards.isNotEmpty && reviewedCount == flashcards.length;

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            'Flashcard review',
            'Tap each card to reveal the definition before the quiz.',
            Icons.style_outlined,
            EduQuestColors.primary,
          ),
          const SizedBox(height: 14),
          Text(
            '$reviewedCount/${flashcards.length} cards revealed',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          ...List.generate(flashcards.length, (index) {
            final card = flashcards[index];
            final isRevealed = revealed.contains(index);
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: InkWell(
                borderRadius: BorderRadius.circular(18),
                onTap: () {
                  setState(() {
                    _revealedFlashcards
                        .putIfAbsent(lessonId, () => <int>{})
                        .add(index);
                  });
                },
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color:
                        isRevealed
                            ? EduQuestColors.primarySoft
                            : EduQuestColors.bg,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color:
                          isRevealed
                              ? EduQuestColors.primary
                              : EduQuestColors.border,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            isRevealed
                                ? Icons.visibility_outlined
                                : Icons.touch_app_outlined,
                            color:
                                isRevealed
                                    ? EduQuestColors.primary
                                    : EduQuestColors.textMuted,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              card['term']?.toString() ?? 'Term',
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                          ),
                          AppInfoChip(
                            label: isRevealed ? 'Revealed' : 'Tap',
                            color:
                                isRevealed
                                    ? EduQuestColors.primary
                                    : EduQuestColors.info,
                          ),
                        ],
                      ),
                      if (isRevealed) ...[
                        const SizedBox(height: 10),
                        Text(
                          card['definition']?.toString() ?? '',
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(color: Colors.white70),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            );
          }),
          if (allRevealed) ...[
            const SizedBox(height: 4),
            AppStatusBanner(
              message:
                  'Flashcards reviewed. You are ready to turn recall into a saved quiz attempt.',
              color: EduQuestColors.success,
              icon: Icons.check_circle_outline,
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _scrollToQuizCta,
              icon: const Icon(Icons.arrow_downward),
              label: const Text('Ready for quiz'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPracticeCard(dynamic lesson, Map<String, dynamic> practice) {
    final lessonId = (lesson['id'] as num?)?.toInt() ?? 0;
    final prompt = practice['prompt']?.toString() ?? '';
    final options = _asStringList(practice['options']);
    final answer = ((practice['answer'] ?? 0) as num).toInt();
    final selected = _practiceSelections[lessonId];
    final checked = _practiceChecked[lessonId] ?? false;
    final isCorrect = checked && selected == answer;

    if (prompt.trim().isEmpty || options.isEmpty) return const SizedBox.shrink();

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            'Mini practice',
            'Answer locally before the quiz. This does not submit an attempt.',
            Icons.extension_outlined,
            EduQuestColors.secondary,
          ),
          const SizedBox(height: 14),
          Text(
            prompt,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          ...List.generate(options.length, (index) {
            final isSelected = selected == index;
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: OutlinedButton(
                onPressed: () {
                  setState(() {
                    _practiceSelections[lessonId] = index;
                    _practiceChecked[lessonId] = false;
                  });
                },
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.all(14),
                  alignment: Alignment.centerLeft,
                  side: BorderSide(
                    color:
                        isSelected
                            ? EduQuestColors.secondary
                            : EduQuestColors.border,
                  ),
                  backgroundColor:
                      isSelected
                          ? EduQuestColors.secondary.withValues(alpha: 0.12)
                          : Colors.transparent,
                ),
                child: Row(
                  children: [
                    Icon(
                      isSelected
                          ? Icons.radio_button_checked
                          : Icons.radio_button_unchecked,
                      color:
                          isSelected
                              ? EduQuestColors.secondary
                              : EduQuestColors.textMuted,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        options[index],
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
          const SizedBox(height: 4),
          ElevatedButton.icon(
            onPressed:
                selected == null
                    ? null
                    : () => setState(() => _practiceChecked[lessonId] = true),
            icon: const Icon(Icons.fact_check_outlined),
            label: const Text('Check answer'),
          ),
          if (checked) ...[
            const SizedBox(height: 12),
            AppStatusBanner(
              message:
                  isCorrect
                      ? 'Correct. ${practice['explanation'] ?? ''}'
                      : 'Not quite. ${practice['explanation'] ?? ''}',
              color: isCorrect ? EduQuestColors.success : EduQuestColors.accent,
              icon: isCorrect ? Icons.check_circle : Icons.lightbulb_outline,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFinalChallengeCard(Map<String, dynamic> challenge) {
    final body = challenge['body']?.toString() ?? '';
    final successCriteria = _asStringList(challenge['successCriteria']);
    if (body.trim().isEmpty && successCriteria.isEmpty) {
      return const SizedBox.shrink();
    }

    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildCardHeader(
            challenge['title']?.toString() ?? 'Final challenge',
            'A small transfer task that connects the lesson to real use.',
            Icons.emoji_events_outlined,
            EduQuestColors.accent,
          ),
          if (body.trim().isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              body,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
            ),
          ],
          if (successCriteria.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              'Success criteria',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            ...successCriteria.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.check_circle_outline,
                      size: 18,
                      color: EduQuestColors.success,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        item,
                        style: Theme.of(context).textTheme.bodySmall
                            ?.copyWith(color: Colors.white70),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCardHeader(
    String title,
    String subtitle,
    IconData icon,
    Color color,
  ) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CircleAvatar(
          radius: 22,
          backgroundColor: color.withValues(alpha: 0.14),
          child: Icon(icon, color: color),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ],
    );
  }

  Map<String, dynamic> _lessonPayload(dynamic lesson) {
    final content = lesson['content']?.toString() ?? '';
    try {
      final decoded = jsonDecode(content);
      if (decoded is Map) {
        return _withLessonFallbacks(Map<String, dynamic>.from(decoded), content);
      }
    } catch (_) {
      // Fall through to plain-text parsing for teacher-created lessons.
    }
    return _withLessonFallbacks(_plainTextPayload(content), content);
  }

  Map<String, dynamic> _withLessonFallbacks(
    Map<String, dynamic> payload,
    String content,
  ) {
    final concepts = _asMapList(payload['concepts']);
    final objectives = _asStringList(payload['objectives']);

    if (_asStringMap(payload['visual']).isEmpty) {
      payload['visual'] = {
        'kind': 'concept-map',
        'title': 'Visual model: concept map',
        'body':
            'Connect the concept, example, practice task, and quiz so the lesson is easier to remember.',
      };
    }

    if (_asMapList(payload['visualBlocks']).isEmpty) {
      payload['visualBlocks'] = [
        {
          'kind': 'learning-loop',
          'title': 'Study loop',
          'body':
              'Read the idea, check the example, practice locally, and submit the quiz for saved progress.',
          'steps': ['learn', 'practice', 'feedback', 'quiz'],
        },
      ];
    }

    if (_asStringMap(payload['didYouKnow']).isEmpty) {
      payload['didYouKnow'] = {
        'title': 'Did you know?',
        'body':
            'The same idea becomes easier to recall when you see it as a definition, visual model, practice task, and quiz explanation.',
      };
    }

    if (_asMapList(payload['flashcards']).isEmpty) {
      payload['flashcards'] = _flashcardsFromConcepts(concepts, objectives);
    }

    if (_asStringMap(payload['finalChallenge']).isEmpty) {
      payload['finalChallenge'] = {
        'title': 'Final challenge',
        'body':
            'Explain this lesson idea in your own words and give one example from the app.',
        'successCriteria': [
          'Use the lesson vocabulary correctly.',
          'Include one concrete example.',
          'Connect your explanation to the quiz feedback.',
        ],
      };
    }

    if ((payload['recap']?.toString() ?? '').trim().isEmpty) {
      payload['recap'] = content;
    }

    return payload;
  }

  Map<String, dynamic> _plainTextPayload(String content) {
    final sections = _splitPlainTextSections(content);
    final intro = sections['Introduction'] ?? content;
    final objectives = _asPlainList(sections['Learning objectives']);
    final concepts =
        _asPlainList(sections['Key concepts'])
            .map((item) => {'title': item, 'body': 'Use this idea in the example and practice task.'})
            .toList();
    final practiceText =
        sections['Mini practice task'] ??
        'Which action best applies the main idea from this lesson?';
    final firstConcept =
        objectives.isNotEmpty
            ? objectives.first
            : concepts.isNotEmpty
            ? concepts.first['title'].toString()
            : 'Apply the lesson concept to a concrete example.';

    return {
      'hook': intro,
      'objectives': objectives,
      'concepts': concepts,
      'explanation': sections['Explanation'] ?? '',
      'example': {
        'title': 'Worked example',
        'kind': _looksLikeCode(sections['Concrete example'] ?? '')
            ? 'code'
            : 'scenario',
        'body': sections['Concrete example'] ?? '',
      },
      'visual': {
        'kind': 'concept-map',
        'title': 'Visual model: concept map',
        'body':
            'Use this card as a visual anchor: concept, example, practice, and quiz are connected.',
      },
      'mistakes': _asPlainList(sections['Common mistakes']),
      'practice': {
        'type': 'mcq',
        'prompt': practiceText,
        'options': [
          firstConcept,
          'Skip the lesson and guess quickly.',
          'Focus only on memorizing the title.',
          'Ignore feedback after answering.',
        ],
        'answer': 0,
        'explanation':
            'The best option applies the lesson idea before moving into the quiz.',
      },
      'recap': sections['Recap'] ?? content,
      'legacyText': content,
    };
  }

  Map<String, String> _splitPlainTextSections(String content) {
    const headings = {
      'Introduction',
      'Learning objectives',
      'Key concepts',
      'Explanation',
      'Concrete example',
      'Common mistakes',
      'Mini practice task',
      'Recap',
    };
    final sections = <String, List<String>>{};
    String? current;
    for (final line in content.split('\n')) {
      final trimmed = line.trim();
      if (headings.contains(trimmed)) {
        current = trimmed;
        sections[current] = [];
      } else if (current != null) {
        sections[current]!.add(line);
      }
    }
    return sections.map(
      (key, value) => MapEntry(key, value.join('\n').trim()),
    );
  }

  List<String> _asPlainList(String? source) {
    if (source == null || source.trim().isEmpty) return [];
    return source
        .split('\n')
        .map((line) => line.trim().replaceFirst(RegExp(r'^[-*]\s*'), ''))
        .where((line) => line.isNotEmpty)
        .toList();
  }

  List<String> _asStringList(dynamic value) {
    if (value is List) {
      return value.map((item) => item.toString()).where((item) => item.isNotEmpty).toList();
    }
    if (value is String) return _asPlainList(value);
    return [];
  }

  List<Map<String, dynamic>> _asMapList(dynamic value) {
    if (value is List) {
      return value.map((item) {
        if (item is Map) return Map<String, dynamic>.from(item);
        return {'title': item.toString(), 'body': ''};
      }).toList();
    }
    return [];
  }

  Map<String, dynamic> _asStringMap(dynamic value) {
    if (value is Map) return Map<String, dynamic>.from(value);
    return {};
  }

  List<Map<String, dynamic>> _flashcardsFromConcepts(
    List<Map<String, dynamic>> concepts,
    List<String> objectives,
  ) {
    final cards = <Map<String, dynamic>>[];
    for (final concept in concepts.take(5)) {
      final term = concept['title']?.toString() ?? '';
      final definition = concept['body']?.toString() ?? '';
      if (term.trim().isNotEmpty && definition.trim().isNotEmpty) {
        cards.add({'term': term, 'definition': definition});
      }
    }
    if (cards.isEmpty) {
      for (final objective in objectives.take(3)) {
        cards.add({
          'term': objective,
          'definition': 'Use this objective as a checkpoint before the quiz.',
        });
      }
    }
    return cards;
  }

  bool _looksLikeCode(String value) {
    return value.contains('\n') ||
        value.contains('=') ||
        value.contains('<') ||
        value.contains('def ') ||
        value.contains('for ') ||
        value.contains('if ');
  }

  IconData _visualIcon(String? kind) {
    switch (kind) {
      case 'client-server':
        return Icons.cloud_sync_outlined;
      case 'box-model':
        return Icons.layers_outlined;
      case 'html-tree':
        return Icons.account_tree_outlined;
      case 'algorithm-steps':
        return Icons.linear_scale_outlined;
      case 'debug-trace':
        return Icons.bug_report_outlined;
      case 'loop-flow':
        return Icons.repeat_outlined;
      case 'python-output':
        return Icons.terminal_outlined;
      case 'forms-validation':
        return Icons.fact_check_outlined;
      case 'learning-loop':
        return Icons.sync_outlined;
      default:
        return Icons.hub_outlined;
    }
  }
}
