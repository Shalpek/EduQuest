import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'ai_review_screen.dart';

class QuizScreen extends StatefulWidget {
  final int lessonId;
  final String lessonTitle;
  final int userId;

  const QuizScreen({
    required this.lessonId,
    required this.lessonTitle,
    required this.userId,
    super.key,
  });

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  List<dynamic> questions = [];
  int currentQuestionIdx = 0;
  List<int> userAnswers = [];
  int correctAnswers = 0;
  bool isLoading = true;
  bool showResult = false;
  Map<String, dynamic>? resultData;
  int? quizId;
  bool retriesEnabled = true;
  String? loadError;

  @override
  void initState() {
    super.initState();
    _loadQuiz();
  }

  Future<void> _loadQuiz() async {
    setState(() {
      isLoading = true;
      loadError = null;
    });

    try {
      final quiz = await ApiService.getQuiz(widget.lessonId);
      final config = await ApiService.getSystemConfig();

      if (!mounted) return;

      setState(() {
        if (config != null) {
          retriesEnabled = config['retries_enabled'] ?? true;
        }
        if (quiz != null && quiz['questions'] != null) {
          quizId = quiz['id'];
          questions = jsonDecode(quiz['questions']);
        } else {
          quizId = 1;
          questions = [
            {
              'q': 'What is a variable?',
              'options': ['A data container', 'A loop', 'A function'],
              'answer': 0,
            },
          ];
        }
        userAnswers = List.filled(questions.length, -1);
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
        loadError = 'Quiz content could not be loaded.';
      });
    }
  }

  Future<void> _submitAnswer(int selectedIdx) async {
    userAnswers[currentQuestionIdx] = selectedIdx;
    final correctIdx = questions[currentQuestionIdx]['answer'];
    if (selectedIdx == correctIdx) {
      correctAnswers++;
    }

    if (currentQuestionIdx < questions.length - 1) {
      setState(() => currentQuestionIdx++);
    } else {
      setState(() => isLoading = true);
      final score = questions.isEmpty ? 0.0 : correctAnswers / questions.length;
      final res = await ApiService.submitQuiz(
        quizId ?? 1,
        widget.userId,
        score,
      );

      await ApiService.completeLesson(widget.userId, widget.lessonId);

      if (!mounted) return;

      setState(() {
        isLoading = false;
        showResult = true;
        resultData =
            res ??
            {
              'xp_earned': (score * 100).toInt(),
              'new_level': 1,
              'feedback_message':
                  'Quiz submitted. Backend-linked feedback will expand in the next pass.',
            };
      });
    }
  }

  void _retryQuiz() {
    setState(() {
      currentQuestionIdx = 0;
      correctAnswers = 0;
      userAnswers = List.filled(questions.length, -1);
      showResult = false;
    });
  }

  List<Map<String, dynamic>> _buildWrongAnswersPayload() {
    final wrongAnswers = <Map<String, dynamic>>[];

    for (var index = 0; index < questions.length; index++) {
      final question = questions[index];
      final userAnswerIdx = userAnswers[index];
      final correctIdx = question['answer'];
      if (userAnswerIdx != correctIdx) {
        wrongAnswers.add({
          'question': question['q'],
          'options': List<String>.from(question['options']),
          'user_answer_index': userAnswerIdx,
          'correct_answer_index': correctIdx,
        });
      }
    }

    return wrongAnswers;
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Preparing quiz session',
          message: 'Loading questions, retry policy, and your result settings.',
        ),
      );
    }

    if (loadError != null) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.lessonTitle)),
        body: AppErrorState(
          title: 'Quiz unavailable',
          description: loadError!,
          onRetry: _loadQuiz,
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.lessonTitle),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: AppInfoChip(
                label: '${currentQuestionIdx + 1}/${questions.length}',
                color: EduQuestColors.secondary,
              ),
            ),
          ),
        ],
      ),
      body: showResult ? _buildResultView() : _buildQuizView(),
    );
  }

  Widget _buildQuizView() {
    final q = questions[currentQuestionIdx];
    final progress = (currentQuestionIdx + 1) / questions.length;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppInfoChip(
                label: 'Accuracy over speed',
                color: EduQuestColors.primary,
                icon: Icons.track_changes_outlined,
              ),
              const SizedBox(height: 14),
              Text(
                'Question ${currentQuestionIdx + 1}',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Use this practice step to reinforce understanding, then review mistakes with AI support if needed.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
              const SizedBox(height: 18),
              LinearProgressIndicator(
                value: progress,
                minHeight: 10,
                borderRadius: BorderRadius.circular(999),
                backgroundColor: EduQuestColors.primarySoft,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(q['q'], style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 18),
              ...List.generate(q['options'].length, (index) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: OutlinedButton(
                    onPressed: () => _submitAnswer(index),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.all(18),
                      alignment: Alignment.centerLeft,
                    ),
                    child: Text(
                      q['options'][index],
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ),
                );
              }),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildResultView() {
    final wrongAnswers = _buildWrongAnswersPayload();
    final totalQuestions = questions.length;
    final double score =
        totalQuestions == 0 ? 0.0 : (correctAnswers / totalQuestions);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
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
                      color:
                          score >= 0.7
                              ? EduQuestColors.success.withValues(alpha: 0.14)
                              : EduQuestColors.accent.withValues(alpha: 0.14),
                    ),
                    child: Icon(
                      score >= 0.7 ? Icons.emoji_events : Icons.auto_fix_high,
                      color:
                          score >= 0.7
                              ? EduQuestColors.success
                              : EduQuestColors.accent,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Quiz complete',
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'You answered $correctAnswers of $totalQuestions correctly.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  AppInfoChip(
                    label: '+${resultData?['xp_earned'] ?? 0} XP',
                    color: EduQuestColors.secondary,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                resultData?['feedback_message']?.toString() ??
                    'Review what went well and what needs another attempt.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
              const SizedBox(height: 18),
              LinearProgressIndicator(
                value: score,
                minHeight: 12,
                borderRadius: BorderRadius.circular(999),
                backgroundColor: EduQuestColors.primarySoft,
                valueColor: AlwaysStoppedAnimation(
                  score >= 0.7 ? EduQuestColors.success : EduQuestColors.accent,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                '${(score * 100).round()}% accuracy • Level ${resultData?['new_level'] ?? 1}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (retriesEnabled)
          AdaptiveTwoPane(
            first: OutlinedButton.icon(
              icon: const Icon(Icons.refresh),
              label: const Text('Retry quiz'),
              onPressed: _retryQuiz,
            ),
            second: ElevatedButton.icon(
              icon: const Icon(Icons.arrow_forward),
              label: const Text('Continue'),
              onPressed: () => Navigator.pop(context),
            ),
          )
        else
          ElevatedButton.icon(
            icon: const Icon(Icons.arrow_forward),
            label: const Text('Continue'),
            onPressed: () => Navigator.pop(context),
          ),
        if (wrongAnswers.isNotEmpty) ...[
          const SizedBox(height: 12),
          ElevatedButton.icon(
            icon: const Icon(Icons.smart_toy_outlined),
            label: const Text('Explain mistakes with AI'),
            style: ElevatedButton.styleFrom(
              backgroundColor: EduQuestColors.info,
            ),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder:
                      (_) => AIReviewScreen(
                        userId: widget.userId,
                        lessonTitle: widget.lessonTitle,
                        wrongAnswers: wrongAnswers,
                      ),
                ),
              );
            },
          ),
        ],
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Answer review',
          subtitle:
              'Use review mode to understand what to repeat and what is already strong.',
        ),
        const SizedBox(height: 12),
        ...List.generate(questions.length, (index) {
          final q = questions[index];
          final userAnswerIdx = userAnswers[index];
          final correctIdx = q['answer'];
          final isCorrect = userAnswerIdx == correctIdx;

          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Card(
              color:
                  isCorrect
                      ? EduQuestColors.success.withValues(alpha: 0.08)
                      : EduQuestColors.accent.withValues(alpha: 0.08),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          isCorrect
                              ? Icons.check_circle
                              : Icons.cancel_outlined,
                          color:
                              isCorrect
                                  ? EduQuestColors.success
                                  : EduQuestColors.accent,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            q['q'],
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Your answer: ${userAnswerIdx >= 0 && userAnswerIdx < q['options'].length ? q['options'][userAnswerIdx] : 'None'}',
                      style: TextStyle(
                        color:
                            isCorrect
                                ? EduQuestColors.success
                                : EduQuestColors.danger,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (!isCorrect) ...[
                      const SizedBox(height: 6),
                      Text(
                        'Correct answer: ${q['options'][correctIdx]}',
                        style: const TextStyle(
                          color: EduQuestColors.success,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        }),
      ],
    );
  }
}
