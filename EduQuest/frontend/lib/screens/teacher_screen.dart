import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'e_mode_screen.dart';
import 'login_screen.dart';

class TeacherScreen extends StatefulWidget {
  final int userId;

  const TeacherScreen({required this.userId, super.key});

  @override
  State<TeacherScreen> createState() => _TeacherScreenState();
}

class _TeacherScreenState extends State<TeacherScreen> {
  static const _destinations = [
    ShellDestination(label: 'Overview', icon: Icons.dashboard_outlined),
    ShellDestination(label: 'Content', icon: Icons.menu_book_outlined),
    ShellDestination(label: 'Assign', icon: Icons.assignment_outlined),
    ShellDestination(label: 'Analytics', icon: Icons.insights_outlined),
    ShellDestination(label: 'Profile', icon: Icons.person_outline),
  ];

  int _selectedIndex = 0;
  List<dynamic> courses = [];
  List<dynamic> studentsProgress = [];
  List<dynamic> recentAttempts = [];
  List<dynamic> assignments = [];
  final Map<int, Map<String, dynamic>> _courseContentCache = {};
  Map<String, dynamic>? overview;
  Map<String, dynamic>? analyticsSummary;
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
      final results = await Future.wait([
        ApiService.getCourses(),
        ApiService.getStudentsProgress(),
        ApiService.getTeacherAttempts(),
        ApiService.getTeacherDashboard(),
        ApiService.getTeacherAssignments(),
        ApiService.getTeacherAnalyticsSummary(),
      ]);

      if (!mounted) return;

      setState(() {
        courses = results[0] as List<dynamic>;
        studentsProgress = results[1] as List<dynamic>;
        recentAttempts = results[2] as List<dynamic>;
        overview = (results[3] as Map<String, dynamic>?)?['overview'];
        assignments = results[4] as List<dynamic>;
        analyticsSummary = results[5] as Map<String, dynamic>?;
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
        loadError = 'Teacher workspace could not load data from the API.';
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

  Future<void> _openEMode() async {
    await Navigator.of(
      context,
    ).push(MaterialPageRoute(builder: (_) => const EModeScreen()));
    if (!mounted) return;
    await _loadData();
  }

  Future<Map<String, dynamic>?> _getCourseContentMap(int courseId) async {
    final cached = _courseContentCache[courseId];
    if (cached != null) return cached;

    final payload = await ApiService.getCourseContentMap(courseId);
    if (payload != null) {
      _courseContentCache[courseId] = payload;
    }
    return payload;
  }

  List<Map<String, dynamic>> _lessonsForCourse(int courseId) {
    final lessons =
        _courseContentCache[courseId]?['lessons'] as List<dynamic>? ??
        const <dynamic>[];
    return lessons.map((lesson) => Map<String, dynamic>.from(lesson)).toList();
  }

  List<Map<String, dynamic>> _quizzesForCourse(int courseId) {
    final lessons = _lessonsForCourse(courseId);
    return lessons.expand((lesson) {
      final lessonTitle = lesson['title']?.toString() ?? 'Lesson';
      final quizzes = lesson['quizzes'] as List<dynamic>? ?? const <dynamic>[];
      return quizzes.map(
        (quiz) => {
          ...Map<String, dynamic>.from(quiz),
          'lesson_id': lesson['id'],
          'lesson_title': lessonTitle,
        },
      );
    }).toList();
  }

  Future<void> _showCreateCourseSheet() async {
    final titleController = TextEditingController();
    final descController = TextEditingController();
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
              'Create course',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Publish a course card with enough structure to feed the mobile learning catalog.',
              style: Theme.of(sheetContext).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: titleController,
              decoration: const InputDecoration(labelText: 'Course title'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descController,
              minLines: 3,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'Description'),
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
                  if (titleController.text.trim().isEmpty) return;
                  final response = await ApiService.createCourse(
                    titleController.text.trim(),
                    descController.text.trim(),
                  );
                  if (!mounted) return;
                  navigator.pop();
                  messenger.showSnackBar(
                    SnackBar(
                      content: Text(
                        response != null
                            ? 'Course "${response['title']}" created'
                            : 'Failed to create course',
                      ),
                    ),
                  );
                  if (response != null) {
                    await _loadData();
                  }
                },
                child: const Text('Create'),
              ),
            ),
          ],
        );
      },
    );
  }

  Future<void> _showCreateLessonSheet() async {
    if (courses.isEmpty) return;
    int selectedCourseId = (courses.first['id'] as num).toInt();
    final titleController = TextEditingController();
    final contentController = TextEditingController();
    final orderController = TextEditingController(text: '1');
    final messenger = ScaffoldMessenger.of(context);

    await showAppModalSheet<void>(
      context: context,
      builder: (sheetContext) {
        final navigator = Navigator.of(sheetContext);
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Create lesson',
                  style: Theme.of(sheetContext).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  'Attach richer reading content to an existing course path.',
                  style: Theme.of(sheetContext).textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<int>(
                  initialValue: selectedCourseId,
                  items:
                      courses
                          .map(
                            (course) => DropdownMenuItem<int>(
                              value: (course['id'] as num).toInt(),
                              child: Text(
                                course['title']?.toString() ?? 'Course',
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: (value) {
                    if (value != null) {
                      setSheetState(() => selectedCourseId = value);
                    }
                  },
                  decoration: const InputDecoration(labelText: 'Course'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: titleController,
                  decoration: const InputDecoration(labelText: 'Lesson title'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: contentController,
                  minLines: 4,
                  maxLines: 7,
                  decoration: const InputDecoration(
                    labelText: 'Lesson content',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: orderController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Order'),
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
                      final response = await ApiService.createLesson(
                        selectedCourseId,
                        titleController.text.trim(),
                        contentController.text.trim(),
                        int.tryParse(orderController.text) ?? 1,
                      );
                      if (!mounted) return;
                      navigator.pop();
                      messenger.showSnackBar(
                        SnackBar(
                          content: Text(
                            response != null
                                ? 'Lesson "${response['title']}" created'
                                : 'Failed to create lesson',
                          ),
                        ),
                      );
                      if (response != null) {
                        _courseContentCache.remove(selectedCourseId);
                        await _loadData();
                      }
                    },
                    child: const Text('Create'),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _showCreateQuizSheet() async {
    if (courses.isEmpty) return;
    int selectedCourseId = (courses.first['id'] as num).toInt();
    await _getCourseContentMap(selectedCourseId);
    if (!mounted) return;
    final availableLessons = _lessonsForCourse(selectedCourseId);
    int? selectedLessonId =
        availableLessons.isNotEmpty
            ? (availableLessons.first['id'] as num).toInt()
            : null;
    final titleController = TextEditingController();
    final xpController = TextEditingController(text: '100');
    final questionController = TextEditingController();
    final codeController = TextEditingController();
    final explanationController = TextEditingController();
    final hintController = TextEditingController();
    final topicController = TextEditingController(text: 'teacher-created');
    final optionControllers = List.generate(4, (_) => TextEditingController());
    final questions = <Map<String, dynamic>>[];
    String questionType = 'mcq';
    String difficulty = 'easy';
    int correctIndex = 0;
    final messenger = ScaffoldMessenger.of(context);

    await showAppModalSheet<void>(
      context: context,
      builder: (sheetContext) {
        final navigator = Navigator.of(sheetContext);
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final lessons = _lessonsForCourse(selectedCourseId);
            final currentOptions =
                questionType == 'true_false'
                    ? const ['True', 'False']
                    : optionControllers
                        .map((controller) => controller.text.trim())
                        .where((value) => value.isNotEmpty)
                        .toList();
            selectedLessonId =
                lessons.any(
                      (lesson) =>
                          (lesson['id'] as num).toInt() == selectedLessonId,
                    )
                    ? selectedLessonId
                    : (lessons.isNotEmpty
                        ? (lessons.first['id'] as num).toInt()
                        : null);

            Map<String, dynamic>? buildDraftQuestion({required bool warn}) {
              final prompt = questionController.text.trim();
              final options =
                  questionType == 'true_false'
                      ? const ['True', 'False']
                      : optionControllers
                          .map((controller) => controller.text.trim())
                          .where((value) => value.isNotEmpty)
                          .toList();
              if (prompt.isEmpty) {
                if (warn) {
                  messenger.showSnackBar(
                    const SnackBar(content: Text('Question text is required')),
                  );
                }
                return null;
              }
              if (options.length < 2) {
                if (warn) {
                  messenger.showSnackBar(
                    const SnackBar(
                      content: Text('Add at least two answer options'),
                    ),
                  );
                }
                return null;
              }
              final safeCorrectIndex =
                  correctIndex.clamp(0, options.length - 1).toInt();
              final question = <String, dynamic>{
                'type': questionType,
                'q': prompt,
                'question': prompt,
                'options': options,
                'answer': safeCorrectIndex,
                'correctIndex': safeCorrectIndex,
                'explanation':
                    explanationController.text.trim().isEmpty
                        ? 'Review the lesson concept and compare it with the selected answer.'
                        : explanationController.text.trim(),
                'difficulty': difficulty,
                'topicTag':
                    topicController.text.trim().isEmpty
                        ? 'teacher-created'
                        : topicController.text.trim(),
                'hint':
                    hintController.text.trim().isEmpty
                        ? 'Look for the option that best matches the lesson objective.'
                        : hintController.text.trim(),
              };
              if (questionType == 'code_output' &&
                  codeController.text.trim().isNotEmpty) {
                question['code'] = codeController.text.trim();
              }
              return question;
            }

            void resetDraft() {
              questionController.clear();
              codeController.clear();
              explanationController.clear();
              hintController.clear();
              topicController.text = 'teacher-created';
              for (final controller in optionControllers) {
                controller.clear();
              }
              correctIndex = 0;
              questionType = 'mcq';
              difficulty = 'easy';
            }

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Create quiz',
                  style: Theme.of(sheetContext).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  'Build a student-ready quiz with fields, options, explanations, hints, and teacher-controlled XP.',
                  style: Theme.of(sheetContext).textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<int>(
                  initialValue: selectedCourseId,
                  items:
                      courses
                          .map(
                            (course) => DropdownMenuItem<int>(
                              value: (course['id'] as num).toInt(),
                              child: Text(
                                course['title']?.toString() ?? 'Course',
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: (value) async {
                    if (value == null) return;
                    await _getCourseContentMap(value);
                    final nextLessons = _lessonsForCourse(value);
                    setSheetState(() {
                      selectedCourseId = value;
                      selectedLessonId =
                          nextLessons.isNotEmpty
                              ? (nextLessons.first['id'] as num).toInt()
                              : null;
                    });
                  },
                  decoration: const InputDecoration(labelText: 'Course'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<int>(
                  initialValue: selectedLessonId,
                  items:
                      lessons
                          .map(
                            (lesson) => DropdownMenuItem<int>(
                              value: (lesson['id'] as num).toInt(),
                              child: Text(
                                lesson['title']?.toString() ?? 'Lesson',
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: (value) {
                    setSheetState(() => selectedLessonId = value);
                  },
                  decoration: const InputDecoration(labelText: 'Lesson'),
                ),
                if (lessons.isEmpty) ...[
                  const SizedBox(height: 12),
                  const AppStatusBanner(
                    message:
                        'This course has no lessons yet. Create a lesson first, then attach a quiz.',
                    color: EduQuestColors.info,
                    icon: Icons.info_outline,
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  controller: titleController,
                  decoration: const InputDecoration(labelText: 'Quiz title'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: xpController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'XP reward',
                    helperText: 'Teacher-controlled reward for this quiz.',
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'Question builder',
                  style: Theme.of(sheetContext).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: questionType,
                  items: const [
                    DropdownMenuItem(
                      value: 'mcq',
                      child: Text('Multiple choice'),
                    ),
                    DropdownMenuItem(
                      value: 'true_false',
                      child: Text('True / false'),
                    ),
                    DropdownMenuItem(
                      value: 'code_output',
                      child: Text('Code output'),
                    ),
                    DropdownMenuItem(
                      value: 'fill_gap',
                      child: Text('Fill gap'),
                    ),
                    DropdownMenuItem(
                      value: 'ordering',
                      child: Text('Ordering'),
                    ),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setSheetState(() {
                      questionType = value;
                      correctIndex = 0;
                    });
                  },
                  decoration: const InputDecoration(labelText: 'Question type'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: questionController,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(labelText: 'Question text'),
                ),
                if (questionType == 'code_output') ...[
                  const SizedBox(height: 12),
                  TextField(
                    controller: codeController,
                    minLines: 3,
                    maxLines: 5,
                    decoration: const InputDecoration(
                      labelText: 'Code block',
                      helperText: 'Optional code shown above the answers.',
                    ),
                  ),
                ],
                if (questionType != 'true_false') ...[
                  const SizedBox(height: 12),
                  ...List.generate(optionControllers.length, (index) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: TextField(
                        controller: optionControllers[index],
                        onChanged: (_) => setSheetState(() {}),
                        decoration: InputDecoration(
                          labelText: 'Option ${index + 1}',
                        ),
                      ),
                    );
                  }),
                ],
                const SizedBox(height: 12),
                DropdownButtonFormField<int>(
                  initialValue:
                      correctIndex < currentOptions.length ? correctIndex : 0,
                  items:
                      List.generate(
                        currentOptions.isEmpty ? 2 : currentOptions.length,
                        (index) => DropdownMenuItem<int>(
                          value: index,
                          child: Text(
                            currentOptions.isNotEmpty
                                ? currentOptions[index]
                                : 'Option ${index + 1}',
                          ),
                        ),
                      ).toList(),
                  onChanged: (value) {
                    setSheetState(() => correctIndex = value ?? 0);
                  },
                  decoration: const InputDecoration(
                    labelText: 'Correct answer',
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: difficulty,
                  items: const [
                    DropdownMenuItem(value: 'easy', child: Text('Easy')),
                    DropdownMenuItem(value: 'medium', child: Text('Medium')),
                    DropdownMenuItem(value: 'hard', child: Text('Hard')),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setSheetState(() => difficulty = value);
                  },
                  decoration: const InputDecoration(labelText: 'Difficulty'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: topicController,
                  decoration: const InputDecoration(labelText: 'Topic tag'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: hintController,
                  decoration: const InputDecoration(labelText: 'Hint'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: explanationController,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: 'Answer explanation',
                  ),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () {
                    final draft = buildDraftQuestion(warn: true);
                    if (draft == null) return;
                    setSheetState(() {
                      questions.add(draft);
                      resetDraft();
                    });
                  },
                  icon: const Icon(Icons.add),
                  label: const Text('Add question'),
                ),
                const SizedBox(height: 12),
                if (questions.isEmpty)
                  const AppStatusBanner(
                    message:
                        'No questions added yet. You can add questions one by one, or create with the current draft.',
                    color: EduQuestColors.info,
                    icon: Icons.info_outline,
                  )
                else
                  ...List.generate(questions.length, (index) {
                    final item = questions[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: AppSurface(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            AppInfoChip(
                              label: '${index + 1}',
                              color: EduQuestColors.secondary,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    item['q']?.toString() ?? 'Question',
                                    style:
                                        Theme.of(context).textTheme.titleSmall,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    '${item['type']} - ${item['difficulty']} - ${item['topicTag']}',
                                    style:
                                        Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            IconButton(
                              tooltip: 'Remove question',
                              onPressed: () {
                                setSheetState(() => questions.removeAt(index));
                              },
                              icon: const Icon(Icons.delete_outline),
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
                const SizedBox(height: 18),
                AdaptiveTwoPane(
                  collapseWidth: 360,
                  first: OutlinedButton(
                    onPressed: () => navigator.pop(),
                    child: const Text('Cancel'),
                  ),
                  second: ElevatedButton(
                    onPressed:
                        selectedLessonId == null
                            ? null
                            : () async {
                              final payload = <Map<String, dynamic>>[
                                ...questions,
                              ];
                              final pendingDraft = buildDraftQuestion(
                                warn: questions.isEmpty,
                              );
                              if (pendingDraft != null) {
                                payload.add(pendingDraft);
                              }
                              final title = titleController.text.trim();
                              final xpReward =
                                  int.tryParse(xpController.text.trim()) ?? -1;
                              if (title.isEmpty) {
                                messenger.showSnackBar(
                                  const SnackBar(
                                    content: Text('Quiz title is required'),
                                  ),
                                );
                                return;
                              }
                              if (payload.isEmpty) {
                                messenger.showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'Add at least one question before creating the quiz',
                                    ),
                                  ),
                                );
                                return;
                              }
                              if (xpReward < 0 || xpReward > 500) {
                                messenger.showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'XP reward must be between 0 and 500',
                                    ),
                                  ),
                                );
                                return;
                              }
                              final response = await ApiService.createQuiz(
                                selectedLessonId!,
                                title,
                                payload,
                                xpReward,
                              );
                              if (!mounted) return;
                              navigator.pop();
                              messenger.showSnackBar(
                                SnackBar(
                                  content: Text(
                                    response != null
                                        ? 'Quiz "${response['title']}" created'
                                        : 'Failed to create quiz',
                                  ),
                                ),
                              );
                              if (response != null) {
                                _courseContentCache.remove(selectedCourseId);
                                await _loadData();
                              }
                            },
                    child: const Text('Create'),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _showAssignmentSheet([Map<String, dynamic>? existing]) async {
    if (courses.isEmpty) return;
    int selectedCourseId =
        existing?['course_id'] != null
            ? (existing!['course_id'] as num).toInt()
            : (courses.first['id'] as num).toInt();
    await _getCourseContentMap(selectedCourseId);
    if (!mounted) return;
    final initialQuizOptions = _quizzesForCourse(selectedCourseId);
    int? selectedQuizId =
        existing?['quiz_id'] != null
            ? (existing!['quiz_id'] as num).toInt()
            : (initialQuizOptions.isNotEmpty
                ? (initialQuizOptions.first['id'] as num).toInt()
                : null);
    final titleController = TextEditingController(
      text: existing?['title']?.toString() ?? '',
    );
    final instructionsController = TextEditingController(
      text: existing?['instructions']?.toString() ?? '',
    );
    final dueController = TextEditingController(
      text: existing?['due_at']?.toString().split('T').first ?? '',
    );
    final messenger = ScaffoldMessenger.of(context);

    await showAppModalSheet<void>(
      context: context,
      builder: (sheetContext) {
        final navigator = Navigator.of(sheetContext);
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final quizOptions = _quizzesForCourse(selectedCourseId);
            selectedQuizId =
                quizOptions.any(
                      (quiz) => (quiz['id'] as num).toInt() == selectedQuizId,
                    )
                    ? selectedQuizId
                    : (quizOptions.isNotEmpty
                        ? (quizOptions.first['id'] as num).toInt()
                        : null);

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  existing == null ? 'Create assignment' : 'Edit assignment',
                  style: Theme.of(sheetContext).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  'Wire teacher task management directly to the backend assignment contracts.',
                  style: Theme.of(sheetContext).textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<int>(
                  initialValue: selectedCourseId,
                  items:
                      courses
                          .map(
                            (course) => DropdownMenuItem<int>(
                              value: (course['id'] as num).toInt(),
                              child: Text(
                                course['title']?.toString() ?? 'Course',
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: (value) async {
                    if (value == null) return;
                    await _getCourseContentMap(value);
                    final nextQuizzes = _quizzesForCourse(value);
                    setSheetState(() {
                      selectedCourseId = value;
                      selectedQuizId =
                          nextQuizzes.isNotEmpty
                              ? (nextQuizzes.first['id'] as num).toInt()
                              : null;
                    });
                  },
                  decoration: const InputDecoration(labelText: 'Course'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<int>(
                  initialValue: selectedQuizId,
                  items:
                      quizOptions
                          .map(
                            (quiz) => DropdownMenuItem<int>(
                              value: (quiz['id'] as num).toInt(),
                              child: Text(
                                '${quiz['title']} (${quiz['lesson_title']}, ${quiz['xp_reward'] ?? 100} XP)',
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: (value) {
                    setSheetState(() => selectedQuizId = value);
                  },
                  decoration: const InputDecoration(labelText: 'Quiz'),
                ),
                if (quizOptions.isEmpty) ...[
                  const SizedBox(height: 12),
                  const AppStatusBanner(
                    message:
                        'This course has no quizzes yet. Create a quiz first, then assign it.',
                    color: EduQuestColors.info,
                    icon: Icons.info_outline,
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  controller: titleController,
                  decoration: const InputDecoration(
                    labelText: 'Assignment title',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: instructionsController,
                  minLines: 3,
                  maxLines: 5,
                  decoration: const InputDecoration(labelText: 'Instructions'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: dueController,
                  decoration: const InputDecoration(
                    labelText: 'Due date (YYYY-MM-DD)',
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
                    onPressed:
                        selectedQuizId == null ||
                                titleController.text.trim().isEmpty
                            ? null
                            : () async {
                              final dueAt =
                                  dueController.text.trim().isEmpty
                                      ? null
                                      : '${dueController.text.trim()}T18:00:00';

                              final response =
                                  existing == null
                                      ? await ApiService.createTeacherAssignment(
                                        quizId: selectedQuizId!,
                                        courseId: selectedCourseId,
                                        title: titleController.text.trim(),
                                        instructions:
                                            instructionsController.text.trim(),
                                        dueAt: dueAt,
                                      )
                                      : await ApiService.updateTeacherAssignment(
                                        assignmentId:
                                            (existing['id'] as num).toInt(),
                                        quizId: selectedQuizId!,
                                        courseId: selectedCourseId,
                                        title: titleController.text.trim(),
                                        instructions:
                                            instructionsController.text.trim(),
                                        dueAt: dueAt,
                                      );

                              if (!mounted) return;
                              navigator.pop();
                              messenger.showSnackBar(
                                SnackBar(
                                  content: Text(
                                    response != null
                                        ? existing == null
                                            ? 'Assignment created'
                                            : 'Assignment updated'
                                        : 'Assignment request failed',
                                  ),
                                ),
                              );
                              if (response != null) {
                                await _loadData();
                              }
                            },
                    child: Text(existing == null ? 'Create' : 'Update'),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _togglePublishAssignment(int assignmentId) async {
    final messenger = ScaffoldMessenger.of(context);
    final response = await ApiService.publishTeacherAssignment(assignmentId);
    if (!mounted) return;
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          response != null
              ? 'Assignment publish state updated'
              : 'Unable to update assignment',
        ),
      ),
    );
    if (response != null) {
      await _loadData();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Loading teacher workspace',
          message: 'Syncing courses, student progress, and classroom activity.',
        ),
      );
    }

    if (loadError != null) {
      return Scaffold(
        body: AppErrorState(
          title: 'Teacher workspace unavailable',
          description: loadError!,
          onRetry: _loadData,
        ),
      );
    }

    return EduQuestShell(
      title: 'Teacher workspace',
      subtitle:
          'Publish content, coordinate assignments, and review classroom signals from one mobile-first shell.',
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
      floatingActionButton:
          _selectedIndex == 1
              ? FloatingActionButton.extended(
                onPressed: _showCreateCourseSheet,
                icon: const Icon(Icons.add),
                label: const Text('New course'),
              )
              : _selectedIndex == 2
              ? FloatingActionButton.extended(
                onPressed: _showAssignmentSheet,
                icon: const Icon(Icons.assignment_add),
                label: const Text('New assignment'),
              )
              : null,
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
        return _buildContentTab();
      case 2:
        return _buildAssignmentsTab();
      case 3:
        return _buildAnalyticsTab();
      case 4:
        return _buildProfileTab();
      default:
        return _buildOverviewTab();
    }
  }

  Widget _buildOverviewTab() {
    final activeCourses = courses.length;
    final activeStudents =
        (overview?['total_students'] as num?)?.toInt() ??
        studentsProgress.length;
    final avgScore =
        ((overview?['average_score'] as num?)?.toDouble() ?? 0) * 100;

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
                    label: 'Teacher control layer',
                    color: EduQuestColors.primary,
                    icon: Icons.school_outlined,
                  ),
                  AppInfoChip(
                    label:
                        '${assignments.where((a) => a['is_published'] == true).length} published assignments',
                    color: EduQuestColors.secondary,
                    icon: Icons.assignment_turned_in_outlined,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                'Class health at a glance',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'This surface stays compact on phone widths while still exposing course activity, student momentum, and recent assessment traffic.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ResponsiveStatsGrid(
          children: [
            AppStatCard(
              label: 'Active courses',
              value: '$activeCourses',
              icon: Icons.menu_book_outlined,
              color: EduQuestColors.primary,
            ),
            AppStatCard(
              label: 'Tracked students',
              value: '$activeStudents',
              icon: Icons.groups_2_outlined,
              color: EduQuestColors.info,
            ),
            AppStatCard(
              label: 'Average score',
              value: '${avgScore.round()}%',
              icon: Icons.analytics_outlined,
              color: EduQuestColors.secondary,
            ),
            AppStatCard(
              label: 'Recent attempts',
              value: '${recentAttempts.length}',
              icon: Icons.fact_check_outlined,
              color: EduQuestColors.success,
            ),
          ],
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Recommended next actions',
          subtitle:
              'Move between authoring, assignment planning, and analytics.',
        ),
        const SizedBox(height: 12),
        AdaptiveTwoPane(
          first: AppActionCard(
            title: 'Publish content',
            subtitle: 'Create a course or lesson shell for the current week.',
            icon: Icons.addchart_outlined,
            color: EduQuestColors.primary,
            onTap: () => setState(() => _selectedIndex = 1),
          ),
          second: AppActionCard(
            title: 'Review analytics',
            subtitle: 'Inspect weak spots and progress signals by learner.',
            icon: Icons.insights_outlined,
            color: EduQuestColors.accent,
            onTap: () => setState(() => _selectedIndex = 3),
          ),
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Recent class activity',
          subtitle:
              'Latest quiz attempts and class movement from the backend feed.',
        ),
        const SizedBox(height: 12),
        if (recentAttempts.isEmpty)
          const AppEmptyState(
            icon: Icons.assignment_outlined,
            title: 'No classroom attempts yet',
            description:
                'As students complete quizzes, this overview will show live attempt traffic.',
          )
        else
          ...recentAttempts.take(5).map(_buildAttemptTile),
      ],
    );
  }

  Widget _buildContentTab() {
    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Content studio',
          subtitle:
              'Manage courses, lessons, and assessment content from one teacher flow.',
        ),
        const SizedBox(height: 12),
        AdaptiveTwoPane(
          first: AppActionCard(
            title: 'Create course',
            subtitle: 'Start a new learning path for a topic or module.',
            icon: Icons.add_box_outlined,
            color: EduQuestColors.primary,
            onTap: _showCreateCourseSheet,
          ),
          second: AppActionCard(
            title: 'Create lesson',
            subtitle: 'Add reading content and order it inside a course.',
            icon: Icons.post_add_outlined,
            color: EduQuestColors.secondary,
            onTap: _showCreateLessonSheet,
          ),
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Create quiz',
          subtitle:
              'Build questions, answer feedback, hints, and XP without raw JSON.',
          icon: Icons.quiz_outlined,
          color: EduQuestColors.info,
          onTap: _showCreateQuizSheet,
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Quiz AI Creator',
          subtitle:
              'Generate an AI quiz draft from uploaded material, lesson content, or teacher instructions, then refine it in chat and save it as a standard quiz.',
          icon: Icons.auto_awesome_outlined,
          color: EduQuestColors.accent,
          onTap: _openEMode,
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Published courses',
          subtitle: 'Current teacher-visible course inventory.',
        ),
        const SizedBox(height: 12),
        if (courses.isEmpty)
          const AppEmptyState(
            icon: Icons.menu_book_outlined,
            title: 'No published courses',
            description:
                'Create the first course to populate this mobile content surface.',
          )
        else
          ...courses.map((course) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppSurface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      course['title']?.toString() ?? 'Course',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      course['description']?.toString() ??
                          'Description missing.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        AppInfoChip(
                          label: '${course['lesson_count'] ?? 0} lessons',
                          color: EduQuestColors.primary,
                          icon: Icons.library_books_outlined,
                        ),
                        AppInfoChip(
                          label: '${course['quiz_count'] ?? 0} quizzes',
                          color: EduQuestColors.info,
                          icon: Icons.quiz_outlined,
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
            );
          }),
      ],
    );
  }

  Widget _buildAssignmentsTab() {
    return ListView(
      children: [
        AppSectionHeader(
          title: 'Assignment planning',
          subtitle:
              'Create, publish, and adjust assignment cards backed by the teacher assignment API.',
          trailing: TextButton.icon(
            onPressed: _showAssignmentSheet,
            icon: const Icon(Icons.add),
            label: const Text('Create'),
          ),
        ),
        const SizedBox(height: 12),
        if (assignments.isEmpty)
          const AppEmptyState(
            icon: Icons.assignment_outlined,
            title: 'No assignments yet',
            description:
                'Create an assignment to turn a quiz into a scheduled student task.',
          )
        else
          ...assignments.map((assignment) {
            final published = assignment['is_published'] == true;
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppSurface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            assignment['title']?.toString() ?? 'Assignment',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        AppInfoChip(
                          label: published ? 'Published' : 'Draft',
                          color:
                              published
                                  ? EduQuestColors.success
                                  : EduQuestColors.secondary,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      assignment['instructions']?.toString().isNotEmpty == true
                          ? assignment['instructions'].toString()
                          : 'No instructions added yet.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        AppInfoChip(
                          label:
                              assignment['course_title']?.toString() ??
                              'Course #${assignment['course_id']}',
                          color: EduQuestColors.primary,
                          icon: Icons.menu_book_outlined,
                        ),
                        AppInfoChip(
                          label:
                              assignment['quiz_title']?.toString() ??
                              'Quiz #${assignment['quiz_id']}',
                          color: EduQuestColors.info,
                          icon: Icons.quiz_outlined,
                        ),
                        AppInfoChip(
                          label:
                              assignment['due_at']
                                  ?.toString()
                                  .split('T')
                                  .first ??
                              'No due date',
                          color: EduQuestColors.secondary,
                          icon: Icons.event_outlined,
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    AdaptiveTwoPane(
                      first: OutlinedButton.icon(
                        onPressed:
                            () => _showAssignmentSheet(
                              Map<String, dynamic>.from(assignment),
                            ),
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Edit'),
                      ),
                      second: ElevatedButton.icon(
                        onPressed:
                            () => _togglePublishAssignment(
                              (assignment['id'] as num).toInt(),
                            ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor:
                              published
                                  ? EduQuestColors.danger
                                  : EduQuestColors.success,
                        ),
                        icon: Icon(
                          published
                              ? Icons.visibility_off_outlined
                              : Icons.publish_outlined,
                        ),
                        label: Text(published ? 'Unpublish' : 'Publish'),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }

  Widget _buildAnalyticsTab() {
    final weakTopics =
        analyticsSummary?['weak_topics'] as List<dynamic>? ?? <dynamic>[];
    final attention =
        analyticsSummary?['students_needing_attention'] as List<dynamic>? ??
        <dynamic>[];
    final averageScore =
        (((analyticsSummary?['average_score'] ?? 0) as num).toDouble() * 100)
            .round();
    final completionRate =
        (((analyticsSummary?['recent_completion_rate'] ?? 0) as num)
                    .toDouble() *
                100)
            .round();

    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Teacher analytics',
          subtitle:
              'Track learner progress, weak topics, and class performance patterns.',
        ),
        const SizedBox(height: 12),
        ResponsiveStatsGrid(
          children: [
            AppStatCard(
              label: 'Average score',
              value: '$averageScore%',
              icon: Icons.analytics_outlined,
              color: EduQuestColors.secondary,
            ),
            AppStatCard(
              label: 'Completion rate',
              value: '$completionRate%',
              icon: Icons.rocket_launch_outlined,
              color: EduQuestColors.success,
            ),
            AppStatCard(
              label: 'Weak topics',
              value: '${weakTopics.length}',
              icon: Icons.report_problem_outlined,
              color: EduQuestColors.accent,
            ),
            AppStatCard(
              label: 'Needs attention',
              value: '${attention.length}',
              icon: Icons.person_search_outlined,
              color: EduQuestColors.info,
            ),
          ],
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Weak topics',
          subtitle:
              'Identify assessments with the lowest average performance first.',
        ),
        const SizedBox(height: 12),
        if (weakTopics.isEmpty)
          const AppEmptyState(
            icon: Icons.insights_outlined,
            title: 'No analytics yet',
            description:
                'As attempts accumulate, the weakest quiz areas will appear here.',
          )
        else
          ...weakTopics.map((topic) => _buildWeakTopicCard(topic)),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Students needing attention',
          subtitle:
              'Spot learners with low scores or missing completion activity.',
        ),
        const SizedBox(height: 12),
        if (attention.isEmpty)
          const AppEmptyState(
            icon: Icons.task_alt_outlined,
            title: 'No intervention list right now',
            description:
                'All tracked students currently have acceptable activity signals.',
          )
        else
          ...attention.map((student) => _buildAttentionCard(student)),
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
                    radius: 28,
                    backgroundColor: EduQuestColors.primarySoft,
                    child: const Icon(Icons.school_outlined),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Teacher account',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Role-aware educator shell for content, assignments, and analytics.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  const AppInfoChip(
                    label: 'Teacher',
                    color: EduQuestColors.primary,
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        AppActionCard(
          title: 'Refresh workspace',
          subtitle: 'Reload course, assignment, and analytics data.',
          icon: Icons.refresh_outlined,
          color: EduQuestColors.info,
          onTap: _loadData,
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Sign out',
          subtitle: 'Return to the shared role-based auth entry.',
          icon: Icons.logout_outlined,
          color: EduQuestColors.danger,
          onTap: _logout,
        ),
      ],
    );
  }

  Widget _buildAttemptTile(dynamic attempt) {
    final score = (((attempt['score'] ?? 0) as num).toDouble() * 100).round();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppSurface(
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: EduQuestColors.surfaceAlt,
              child: Text('$score%'),
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
                    '${attempt['user_name'] ?? 'Student'} • ${attempt['earned_xp'] ?? 0} XP earned',
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

  Widget _buildWeakTopicCard(dynamic topic) {
    final average =
        (((topic['average_score'] ?? 0) as num).toDouble() * 100).round();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppSurface(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              topic['quiz_title']?.toString() ?? 'Quiz',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Current average score: $average%',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: ((topic['average_score'] ?? 0) as num).toDouble().clamp(
                0.0,
                1.0,
              ),
              minHeight: 8,
              borderRadius: BorderRadius.circular(999),
              backgroundColor: EduQuestColors.primarySoft,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAttentionCard(dynamic student) {
    final average =
        (((student['average_score'] ?? 0) as num).toDouble() * 100).round();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppSurface(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              student['name']?.toString() ?? 'Student',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                AppInfoChip(
                  label: '$average% average',
                  color: EduQuestColors.secondary,
                ),
                AppInfoChip(
                  label:
                      '${student['completed_lessons'] ?? 0} completed lessons',
                  color: EduQuestColors.info,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
