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
  int xpReward = 100;
  bool retriesEnabled = true;
  String? loadError;
  String? errorTitle;
  final Map<int, String> _fillGapInputs = {};
  final Set<int> _visibleHints = {};

  @override
  void initState() {
    super.initState();
    _loadQuiz();
  }

  Future<void> _loadQuiz() async {
    setState(() {
      isLoading = true;
      loadError = null;
      errorTitle = null;
    });

    try {
      final quiz = await ApiService.getQuiz(widget.lessonId);
      final config = await ApiService.getAppConfig();

      if (!mounted) return;

      if (quiz == null || quiz['questions'] == null || quiz['id'] == null) {
        setState(() {
          isLoading = false;
          errorTitle = 'Quiz unavailable';
          loadError = 'Quiz content could not be loaded from the backend.';
        });
        return;
      }

      final decodedQuestions = jsonDecode(quiz['questions'].toString());
      if (decodedQuestions is! List || decodedQuestions.isEmpty) {
        setState(() {
          isLoading = false;
          errorTitle = 'Quiz unavailable';
          loadError = 'This lesson does not have published quiz questions yet.';
        });
        return;
      }

      setState(() {
        if (config != null) {
          retriesEnabled = config['retries_enabled'] ?? true;
        }
        quizId = (quiz['id'] as num).toInt();
        xpReward = ((quiz['xp_reward'] ?? 100) as num).toInt();
        questions = decodedQuestions;
        userAnswers = List.filled(questions.length, -1);
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
        errorTitle = 'Quiz unavailable';
        loadError = 'Quiz content could not be loaded.';
      });
    }
  }

  Future<void> _submitAnswer(int selectedIdx) async {
    userAnswers[currentQuestionIdx] = selectedIdx;
    final correctIdx = _correctIndex(questions[currentQuestionIdx]);
    if (selectedIdx == correctIdx) {
      correctAnswers++;
    }

    if (currentQuestionIdx < questions.length - 1) {
      setState(() => currentQuestionIdx++);
    } else {
      setState(() => isLoading = true);
      if (quizId == null) {
        if (!mounted) return;
        setState(() {
          isLoading = false;
          errorTitle = 'Quiz result not saved';
          loadError =
              'The quiz session is missing a backend quiz id. Reload the lesson and try again.';
        });
        return;
      }

      final res = await ApiService.submitQuiz(quizId!, List<int>.from(userAnswers));

      if (!mounted) return;

      if (res == null) {
        setState(() {
          isLoading = false;
          errorTitle = 'Quiz result not saved';
          loadError =
              'Quiz submission failed. Your attempt was not saved, so XP and progress were not updated.';
        });
        return;
      }

      setState(() {
        isLoading = false;
        showResult = true;
        resultData = res;
        correctAnswers =
            ((res['correct_answers'] ?? correctAnswers) as num).toInt();
      });
    }
  }

  Future<void> _submitFillGapAnswer() async {
    final q = questions[currentQuestionIdx];
    final options = _options(q);
    final typed = _fillGapInputs[currentQuestionIdx] ?? '';
    final selectedIdx = _matchingOptionIndex(typed, options);
    if (selectedIdx < 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Type one of the expected answers before submitting.'),
        ),
      );
      return;
    }
    await _submitAnswer(selectedIdx);
  }

  void _retryQuiz() {
    setState(() {
      currentQuestionIdx = 0;
      correctAnswers = 0;
      userAnswers = List.filled(questions.length, -1);
      _fillGapInputs.clear();
      _visibleHints.clear();
      showResult = false;
    });
  }

  void _openAiReview({int? questionIndex}) {
    final attemptId = ((resultData?['attempt_id'] ?? 0) as num).toInt();
    if (attemptId <= 0) {
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => AIReviewScreen(
              userId: widget.userId,
              attemptId: attemptId,
              lessonTitle: widget.lessonTitle,
              questionIndex: questionIndex,
            ),
      ),
    );
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
          title: errorTitle ?? 'Quiz unavailable',
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
    final type = q['type']?.toString() ?? 'mcq';
    final difficulty = q['difficulty']?.toString();
    final topicTag = q['topicTag']?.toString();
    final hint = q['hint']?.toString() ?? '';
    final showHint = _visibleHints.contains(currentQuestionIdx);

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
              const SizedBox(height: 10),
              AppInfoChip(
                label: '$xpReward XP max',
                color: EduQuestColors.secondary,
                icon: Icons.bolt_outlined,
              ),
              if (type != 'mcq') ...[
                const SizedBox(height: 10),
                AppInfoChip(
                  label: type,
                  color: EduQuestColors.info,
                  icon: Icons.extension_outlined,
                ),
              ],
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
              Text(_questionText(q), style: Theme.of(context).textTheme.titleLarge),
              if (difficulty != null || topicTag != null) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    if (difficulty != null)
                      AppInfoChip(
                        label: difficulty,
                        color: EduQuestColors.secondary,
                        icon: Icons.speed_outlined,
                      ),
                    if (topicTag != null)
                      AppInfoChip(
                        label: topicTag,
                        color: EduQuestColors.info,
                        icon: Icons.sell_outlined,
                      ),
                  ],
                ),
              ],
              if (q['code'] != null) ...[
                const SizedBox(height: 14),
                _buildCodeBlock(q['code'].toString()),
              ],
              if (hint.isNotEmpty) ...[
                const SizedBox(height: 14),
                OutlinedButton.icon(
                  onPressed: () {
                    setState(() => _visibleHints.add(currentQuestionIdx));
                  },
                  icon: const Icon(Icons.lightbulb_outline),
                  label: const Text('Show hint'),
                ),
                if (showHint) ...[
                  const SizedBox(height: 10),
                  AppStatusBanner(
                    message: hint,
                    color: EduQuestColors.info,
                    icon: Icons.smart_toy_outlined,
                  ),
                ],
              ],
              const SizedBox(height: 18),
              _buildQuestionInput(q),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildResultView() {
    final totalQuestions = questions.length;
    final localScore = totalQuestions == 0 ? 0.0 : correctAnswers / totalQuestions;
    final double score =
        ((resultData?['score'] ?? localScore) as num).toDouble();

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
                '${(score * 100).round()}% accuracy | Level ${resultData?['new_level'] ?? 1}',
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
        if ((resultData?['wrong_answer_indexes'] as List<dynamic>? ?? []).isNotEmpty) ...[
          const SizedBox(height: 12),
          ElevatedButton.icon(
            icon: const Icon(Icons.smart_toy_outlined),
            label: const Text('Explain mistakes with AI'),
            style: ElevatedButton.styleFrom(
              backgroundColor: EduQuestColors.info,
            ),
            onPressed: _openAiReview,
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
          final correctIdx = _correctIndex(q);
          final isCorrect = userAnswerIdx == correctIdx;
          final explanation = q['explanation']?.toString() ?? '';
          final difficulty = q['difficulty']?.toString();
          final topicTag = q['topicTag']?.toString();
          final options = _options(q);

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
                            _questionText(q),
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Your answer: ${userAnswerIdx >= 0 && userAnswerIdx < options.length ? options[userAnswerIdx] : 'None'}',
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
                        'Correct answer: ${correctIdx >= 0 && correctIdx < options.length ? options[correctIdx] : 'Unknown'}',
                        style: const TextStyle(
                          color: EduQuestColors.success,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.smart_toy_outlined),
                          label: const Text('Review this mistake with AI'),
                          onPressed: () => _openAiReview(questionIndex: index),
                        ),
                      ),
                    ],
                    if (difficulty != null || topicTag != null) ...[
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          if (difficulty != null)
                            AppInfoChip(
                              label: difficulty,
                              color: EduQuestColors.secondary,
                              icon: Icons.speed_outlined,
                            ),
                          if (topicTag != null)
                            AppInfoChip(
                              label: topicTag,
                              color: EduQuestColors.info,
                              icon: Icons.sell_outlined,
                            ),
                        ],
                      ),
                    ],
                    if (explanation.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Container(
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
                            Text(
                              'Explanation',
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                            const SizedBox(height: 6),
                            Text(
                              explanation,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
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

  Widget _buildQuestionInput(dynamic question) {
    final type = question is Map ? question['type']?.toString() ?? 'mcq' : 'mcq';
    switch (type) {
      case 'fill_gap':
        return _buildFillGapInput(question);
      case 'ordering':
        return _buildOptionButtons(question, ordered: true);
      case 'true_false':
      case 'code_output':
      case 'mcq':
      default:
        return _buildOptionButtons(question);
    }
  }

  Widget _buildOptionButtons(dynamic question, {bool ordered = false}) {
    final options = _options(question);
    return Column(
      children: List.generate(options.length, (index) {
        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: OutlinedButton(
            onPressed: () => _submitAnswer(index),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.all(18),
              alignment: Alignment.centerLeft,
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (ordered) ...[
                  AppInfoChip(
                    label: '${index + 1}',
                    color: EduQuestColors.secondary,
                  ),
                  const SizedBox(width: 10),
                ],
                Expanded(
                  child: Text(
                    options[index],
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ),
              ],
            ),
          ),
        );
      }),
    );
  }

  Widget _buildFillGapInput(dynamic question) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          key: ValueKey('fill-gap-$currentQuestionIdx'),
          onChanged: (value) => _fillGapInputs[currentQuestionIdx] = value,
          decoration: InputDecoration(
            labelText: 'Type the missing word',
            helperText: 'Use the lesson keyword exactly.',
          ),
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _submitFillGapAnswer(),
        ),
        const SizedBox(height: 12),
        ElevatedButton.icon(
          onPressed: _submitFillGapAnswer,
          icon: const Icon(Icons.check),
          label: const Text('Submit answer'),
        ),
      ],
    );
  }

  Widget _buildCodeBlock(String code) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: EduQuestColors.bg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: EduQuestColors.border),
      ),
      child: Text(
        code,
        style: const TextStyle(
          color: Colors.white70,
          fontFamily: 'monospace',
          height: 1.45,
        ),
      ),
    );
  }

  String _questionText(dynamic question) {
    if (question is Map) {
      return question['q']?.toString() ??
          question['question']?.toString() ??
          'Question';
    }
    return 'Question';
  }

  int _correctIndex(dynamic question) {
    if (question is Map) {
      final answer = question['answer'] ?? question['correctIndex'] ?? 0;
      if (answer is num) return answer.toInt();
    }
    return 0;
  }

  List<String> _options(dynamic question) {
    if (question is Map && question['options'] is List) {
      return List<String>.from(question['options'] as List);
    }
    return const [];
  }

  int _matchingOptionIndex(String input, List<String> options) {
    final normalized = input.trim().toLowerCase();
    if (normalized.isEmpty) return -1;
    for (var index = 0; index < options.length; index++) {
      if (options[index].trim().toLowerCase() == normalized) return index;
    }
    return -1;
  }
}
