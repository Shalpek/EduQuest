import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';

class EModeScreen extends StatefulWidget {
  const EModeScreen({super.key});

  @override
  State<EModeScreen> createState() => _EModeScreenState();
}

class _EModeScreenState extends State<EModeScreen> {
  static const _supportedTypes = [
    'mcq',
    'true_false',
    'code_output',
    'fill_gap',
    'ordering',
  ];

  final _topicController = TextEditingController();
  final _instructionsController = TextEditingController();
  final _quizTitleController = TextEditingController();
  final _taskCountController = TextEditingController(text: '5');
  final _chatController = TextEditingController();

  bool _loading = true;
  bool _busy = false;
  String? _loadError;
  List<dynamic> _courses = [];
  final Map<int, Map<String, dynamic>> _courseContentCache = {};
  int? _selectedCourseId;
  int? _selectedLessonId;
  String _difficulty = 'medium';
  String _studentLevel = 'beginner';
  String _language = 'English';
  final Set<String> _preferredTypes = {'mcq', 'true_false'};
  String? _selectedFileName;
  List<int>? _selectedFileBytes;
  Map<String, dynamic>? _session;

  @override
  void initState() {
    super.initState();
    _loadCourses();
  }

  @override
  void dispose() {
    _topicController.dispose();
    _instructionsController.dispose();
    _quizTitleController.dispose();
    _taskCountController.dispose();
    _chatController.dispose();
    super.dispose();
  }

  Future<void> _loadCourses() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    final courses = await ApiService.getCourses();
    if (!mounted) return;
    if (courses.isEmpty) {
      setState(() {
        _loading = false;
        _loadError = 'No courses available for Quiz AI Creator.';
      });
      return;
    }
    final initialCourseId = (courses.first['id'] as num).toInt();
    await _ensureCourseContent(initialCourseId);
    if (!mounted) return;
    final lessons = _lessonsForCourse(initialCourseId);
    setState(() {
      _courses = courses;
      _selectedCourseId = initialCourseId;
      _selectedLessonId =
          lessons.isNotEmpty ? (lessons.first['id'] as num).toInt() : null;
      _loading = false;
    });
  }

  Future<void> _ensureCourseContent(int courseId) async {
    if (_courseContentCache.containsKey(courseId)) return;
    final payload = await ApiService.getCourseContentMap(courseId);
    if (payload != null) {
      _courseContentCache[courseId] = payload;
    }
  }

  List<Map<String, dynamic>> _lessonsForCourse(int courseId) {
    final lessons =
        _courseContentCache[courseId]?['lessons'] as List<dynamic>? ??
        const <dynamic>[];
    return lessons.map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'txt', 'docx'],
      withData: true,
    );
    if (result == null || result.files.isEmpty) return;
    final file = result.files.single;
    List<int>? bytes = file.bytes;
    if (bytes == null && file.path != null) {
      bytes = await File(file.path!).readAsBytes();
    }
    if (bytes == null || bytes.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to read the selected file')),
      );
      return;
    }
    setState(() {
      _selectedFileName = file.name;
      _selectedFileBytes = bytes;
    });
  }

  Future<void> _startGeneration() async {
    if (_selectedLessonId == null || _selectedCourseId == null) {
      _showMessage('Select a course and lesson first');
      return;
    }
    if (_topicController.text.trim().isEmpty) {
      _showMessage('Topic is required');
      return;
    }
    setState(() => _busy = true);
    final created = await ApiService.createEModeSession(
      courseId: _selectedCourseId!,
      lessonId: _selectedLessonId!,
      topic: _topicController.text.trim(),
      instructions: _instructionsController.text.trim(),
      studentLevel: _studentLevel,
      difficulty: _difficulty,
      language: _language,
      taskCount: int.tryParse(_taskCountController.text.trim()),
      preferredTypes: _preferredTypes.toList(),
      quizTitle: _quizTitleController.text.trim().isEmpty
          ? null
          : _quizTitleController.text.trim(),
    );
    if (!mounted) return;
    if (created['error'] != null) {
      setState(() => _busy = false);
      _showMessage(created['error'].toString());
      return;
    }

    if (_selectedFileBytes != null && _selectedFileName != null) {
      final uploaded = await ApiService.uploadEModeMaterial(
        sessionId: (created['id'] as num).toInt(),
        fileName: _selectedFileName!,
        bytes: _selectedFileBytes!,
      );
      if (!mounted) return;
      if (uploaded['error'] != null) {
        setState(() => _busy = false);
        _showMessage(uploaded['error'].toString());
        return;
      }
    }

    final generated = await ApiService.generateEModeDraft(
      (created['id'] as num).toInt(),
    );
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (generated['error'] == null) {
        _session = generated;
      }
    });
    if (generated['error'] != null) {
      _showMessage(generated['error'].toString());
      return;
    }
    _showMessage('Quiz AI Creator draft generated');
  }

  Future<void> _sendChatMessage() async {
    final message = _chatController.text.trim();
    final sessionId = (_session?['id'] as num?)?.toInt();
    if (sessionId == null || message.isEmpty || _busy) return;
    setState(() => _busy = true);
    final updated = await ApiService.chatEModeSession(
      sessionId: sessionId,
      message: message,
    );
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (updated['error'] == null) {
        _session = updated;
        _chatController.clear();
      }
    });
    if (updated['error'] != null) {
      _showMessage(updated['error'].toString());
      return;
    }
  }

  Future<void> _saveDraft() async {
    final sessionId = (_session?['id'] as num?)?.toInt();
    if (sessionId == null) return;
    setState(() => _busy = true);
    final saved = await ApiService.saveEModeDraft(sessionId: sessionId);
    if (!mounted) return;
    setState(() => _busy = false);
    if (saved['error'] != null) {
      _showMessage(saved['error'].toString());
      return;
    }
    final quiz = saved['quiz'] as Map<String, dynamic>? ?? const {};
    _showMessage('Quiz "${quiz['title'] ?? 'Untitled'}" saved to the lesson');
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Opening Quiz AI Creator',
          message: 'Loading course structure, lessons, and AI draft controls.',
        ),
      );
    }

    if (_loadError != null) {
      return Scaffold(
        body: AppErrorState(
          title: 'Quiz AI Creator unavailable',
          description: _loadError!,
          onRetry: _loadCourses,
        ),
      );
    }

    return EduQuestShell(
      title: 'Quiz AI Creator',
      subtitle:
          'Generate quiz drafts from uploaded materials, lesson content, or teacher instructions, then refine them in chat before saving.',
      currentIndex: 1,
      destinations: const [
        ShellDestination(label: 'Back', icon: Icons.arrow_back),
        ShellDestination(label: 'Quiz AI Creator', icon: Icons.auto_awesome),
      ],
      onSelect: (index) {
        if (index == 0) Navigator.of(context).pop();
      },
      actions: [
        IconButton(
          tooltip: 'Refresh session',
          onPressed: _session == null
              ? null
              : () async {
                  final refreshed = await ApiService.getEModeSession(
                    (_session!['id'] as num).toInt(),
                  );
                  if (!mounted) return;
                  if (refreshed['error'] == null) {
                    setState(() => _session = refreshed);
                  } else {
                    _showMessage(refreshed['error'].toString());
                  }
                },
          icon: const Icon(Icons.refresh),
        ),
      ],
      child: ListView(
        children: [
          _buildSetupCard(),
          const SizedBox(height: 16),
          _buildDraftCard(),
          const SizedBox(height: 16),
          _buildChatCard(),
        ],
      ),
    );
  }

  Widget _buildSetupCard() {
    final lessons =
        _selectedCourseId == null ? const <Map<String, dynamic>>[] : _lessonsForCourse(_selectedCourseId!);
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AppSectionHeader(
            title: 'Draft setup',
            subtitle:
                'Choose where the final quiz will live, optionally upload material, and set generation preferences.',
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<int>(
            initialValue: _selectedCourseId,
            items: _courses
                .map(
                  (course) => DropdownMenuItem<int>(
                    value: (course['id'] as num).toInt(),
                    child: Text(course['title']?.toString() ?? 'Course'),
                  ),
                )
                .toList(),
            onChanged: (value) async {
              if (value == null) return;
              await _ensureCourseContent(value);
              final nextLessons = _lessonsForCourse(value);
              if (!mounted) return;
              setState(() {
                _selectedCourseId = value;
                _selectedLessonId = nextLessons.isNotEmpty
                    ? (nextLessons.first['id'] as num).toInt()
                    : null;
              });
            },
            decoration: const InputDecoration(labelText: 'Course'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(
            initialValue: _selectedLessonId,
            items: lessons
                .map(
                  (lesson) => DropdownMenuItem<int>(
                    value: (lesson['id'] as num).toInt(),
                    child: Text(lesson['title']?.toString() ?? 'Lesson'),
                  ),
                )
                .toList(),
            onChanged: (value) => setState(() => _selectedLessonId = value),
            decoration: const InputDecoration(labelText: 'Lesson'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _topicController,
            decoration: const InputDecoration(labelText: 'Topic'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _quizTitleController,
            decoration: const InputDecoration(labelText: 'Optional quiz title'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _instructionsController,
            minLines: 3,
            maxLines: 5,
            decoration: const InputDecoration(
              labelText: 'Teacher instructions',
              helperText:
                  'Optional guidance such as level, focus, assessment purpose, or requested changes.',
            ),
          ),
          const SizedBox(height: 12),
          AdaptiveTwoPane(
            first: DropdownButtonFormField<String>(
              initialValue: _studentLevel,
              items: const [
                DropdownMenuItem(value: 'beginner', child: Text('Beginner')),
                DropdownMenuItem(value: 'intermediate', child: Text('Intermediate')),
                DropdownMenuItem(value: 'advanced', child: Text('Advanced')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _studentLevel = value);
              },
              decoration: const InputDecoration(labelText: 'Student level'),
            ),
            second: DropdownButtonFormField<String>(
              initialValue: _difficulty,
              items: const [
                DropdownMenuItem(value: 'easy', child: Text('Easy')),
                DropdownMenuItem(value: 'medium', child: Text('Medium')),
                DropdownMenuItem(value: 'hard', child: Text('Hard')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _difficulty = value);
              },
              decoration: const InputDecoration(labelText: 'Target difficulty'),
            ),
          ),
          const SizedBox(height: 12),
          AdaptiveTwoPane(
            first: TextField(
              controller: _taskCountController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Question count'),
            ),
            second: DropdownButtonFormField<String>(
              initialValue: _language,
              items: const [
                DropdownMenuItem(value: 'English', child: Text('English')),
                DropdownMenuItem(value: 'Russian', child: Text('Russian')),
                DropdownMenuItem(value: 'Kazakh', child: Text('Kazakh')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _language = value);
              },
              decoration: const InputDecoration(labelText: 'Language'),
            ),
          ),
          const SizedBox(height: 14),
          Text(
            'Preferred question types',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _supportedTypes.map((type) {
              final selected = _preferredTypes.contains(type);
              return FilterChip(
                selected: selected,
                label: Text(type),
                onSelected: (value) {
                  setState(() {
                    if (value) {
                      _preferredTypes.add(type);
                    } else {
                      _preferredTypes.remove(type);
                    }
                  });
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          AdaptiveTwoPane(
            first: OutlinedButton.icon(
              onPressed: _busy ? null : _pickFile,
              icon: const Icon(Icons.upload_file_outlined),
              label: Text(_selectedFileName ?? 'Optional PDF / TXT / DOCX'),
            ),
            second: ElevatedButton.icon(
              onPressed: _busy ? null : _startGeneration,
              icon: _busy
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.auto_awesome),
              label: Text(_session == null ? 'Start Quiz AI Creator' : 'Start new draft'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDraftCard() {
    final draft = _session?['draft'] as Map<String, dynamic>?;
    final questions = draft?['questions'] as List<dynamic>? ?? const [];
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AppSectionHeader(
            title: 'Current draft',
            subtitle:
                'Preview the generated quiz before you save it into the selected lesson.',
            trailing: ElevatedButton.icon(
              onPressed: (_busy || draft == null) ? null : _saveDraft,
              icon: const Icon(Icons.save_outlined),
              label: const Text('Save as quiz'),
            ),
          ),
          const SizedBox(height: 12),
          if (draft == null)
            const AppEmptyState(
              icon: Icons.description_outlined,
              title: 'No draft yet',
              description:
                  'Start Quiz AI Creator with optional upload to generate the first quiz draft.',
            )
          else ...[
            AppInfoChip(
              label: _selectedFileName != null
                  ? 'Using uploaded material'
                  : ((_session?['generation_source']?.toString() == 'lesson_content')
                        ? 'Using lesson content'
                        : 'Using teacher instructions only'),
              color: EduQuestColors.info,
            ),
            const SizedBox(height: 12),
            Text(
              draft['title']?.toString() ?? 'Untitled draft',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                AppInfoChip(
                  label: '${draft['xp_reward'] ?? 100} XP',
                  color: EduQuestColors.secondary,
                  icon: Icons.stars_outlined,
                ),
                AppInfoChip(
                  label: '${questions.length} questions',
                  color: EduQuestColors.primary,
                  icon: Icons.quiz_outlined,
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...List.generate(questions.length, (index) {
              final question = Map<String, dynamic>.from(questions[index]);
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: AppSurface(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          AppInfoChip(
                            label: '${index + 1}',
                            color: EduQuestColors.info,
                          ),
                          const SizedBox(width: 8),
                          AppInfoChip(
                            label: question['type']?.toString() ?? 'mcq',
                            color: EduQuestColors.secondary,
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        question['q']?.toString() ?? 'Question',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      if (question['code'] != null) ...[
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: EduQuestColors.bg,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: EduQuestColors.border),
                          ),
                          child: Text(
                            question['code'].toString(),
                            style: const TextStyle(fontFamily: 'monospace'),
                          ),
                        ),
                        const SizedBox(height: 8),
                      ],
                      ...(question['options'] as List<dynamic>? ?? const [])
                          .map(
                            (option) => Padding(
                              padding: const EdgeInsets.only(bottom: 6),
                              child: Text('- ${option.toString()}'),
                            ),
                          ),
                    ],
                  ),
                ),
              );
            }),
          ],
        ],
      ),
    );
  }

  Widget _buildChatCard() {
    final messages = _session?['messages'] as List<dynamic>? ?? const [];
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AppSectionHeader(
            title: 'Draft chat',
            subtitle:
                'Use follow-up instructions like "make it easier" or "add more true/false questions".',
          ),
          const SizedBox(height: 12),
          if (_session == null)
            const AppEmptyState(
              icon: Icons.chat_bubble_outline,
              title: 'No active Quiz AI Creator session',
              description:
                  'Generate the first draft before using the chat-based editing flow.',
            )
          else ...[
            Container(
              constraints: const BoxConstraints(maxHeight: 340),
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: messages.length,
                itemBuilder: (context, index) {
                  final message = Map<String, dynamic>.from(messages[index]);
                  final teacher = message['role'] == 'teacher';
                  return Align(
                    alignment:
                        teacher ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.all(14),
                      constraints: BoxConstraints(
                        maxWidth: MediaQuery.of(context).size.width * 0.8,
                      ),
                      decoration: BoxDecoration(
                        color: teacher
                            ? EduQuestColors.primary
                            : EduQuestColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: Text(message['content']?.toString() ?? ''),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _chatController,
                    minLines: 1,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      hintText: 'Make it easier. Add more true/false. Use only file facts...',
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  height: 56,
                  width: 56,
                  child: ElevatedButton(
                    onPressed: _busy ? null : _sendChatMessage,
                    child: const Icon(Icons.send),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
